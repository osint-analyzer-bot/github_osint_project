import threading
import subprocess
import json
import os

from .email_utils import EmailNotifier
from .models import ScanRequest, ScanResult
from .utils import download_github_repository, cleanup_repository
import logging

logger = logging.getLogger(__name__)


class ScanProcessor:
    @staticmethod
    def get_trufflehog_version():
        """Определяет версию TruffleHog"""
        try:
            result = subprocess.run(
                ["trufflehog", "--version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                version_output = result.stdout.strip().lower()
                logger.info(f"TruffleHog version output: {version_output}")
                if "v3" in version_output or "version 3" in version_output:
                    return "v3"
                else:
                    return "v2"
            return "unknown"
        except Exception as e:
            logger.warning(f"Не удалось определить версию TruffleHog: {e}")
            return "unknown"

    @staticmethod
    def process_scan(scan_request_id):
        """
        Обрабатывает сканирование в отдельном потоке
        """
        scan_request = None
        repo_path = None

        try:
            # Получаем объект сканирования
            scan_request = ScanRequest.objects.get(id=scan_request_id)
            logger.info(f"=== НАЧАЛО СКАНИРОВАНИЯ {scan_request_id} ===")

            # Определяем версию TruffleHog
            trufflehog_version = ScanProcessor.get_trufflehog_version()
            logger.info(f"Обнаружена версия TruffleHog: {trufflehog_version}")

            # Обновляем статус на скачивание
            scan_request.status = "DOWNLOADING"
            scan_request.save()

            # Скачиваем репозиторий
            repo_path = download_github_repository(
                scan_request.repository_url,
                include_history=scan_request.include_history,
            )

            if not repo_path:
                logger.error("Не удалось скачать репозиторий")
                scan_request.status = "FAILED"
                scan_request.error_message = "Не удалось скачать репозиторий"
                scan_request.save()

                # Отправляем уведомление об ошибке
                EmailNotifier.send_scan_error_notification(
                    scan_request, "Не удалось скачать репозиторий"
                )
                return

            # Сохраняем локальный путь и обновляем статус
            scan_request.local_path = repo_path
            scan_request.status = "SCANNING"
            scan_request.save()

            # Запускаем сканирование с передачей версии TruffleHog
            if scan_request.scan_type == "SECRETS":
                ScanProcessor._scan_secrets(
                    scan_request, repo_path, trufflehog_version
                )  # ← ДОБАВЬТЕ АРГУМЕНТ
            else:
                ScanProcessor._scan_dependencies(scan_request, repo_path)

            scan_request.status = "COMPLETED"
            scan_request.save()

            logger.info(f"=== СКАНИРОВАНИЕ {scan_request_id} ЗАВЕРШЕНО ===")

            # Отправляем уведомление о завершении сканирования
            EmailNotifier.send_scan_completion_notification(scan_request)

        except Exception as e:
            logger.error(f"ОШИБКА при обработке сканирования {scan_request_id}: {e}")
            if scan_request:
                scan_request.status = "FAILED"
                scan_request.error_message = str(e)
                scan_request.save()

                # Отправляем уведомление об ошибке
                EmailNotifier.send_scan_error_notification(scan_request, str(e))
        finally:
            # Очищаем временные файлы
            if repo_path:
                try:
                    cleanup_repository(repo_path)
                except Exception as cleanup_error:
                    logger.error(
                        f"Ошибка при очистке временных файлов: {cleanup_error}"
                    )

    @staticmethod
    def _scan_secrets(scan_request, repo_path, trufflehog_version):
        """
        Сканирует репозиторий на наличие секретов с помощью TruffleHog
        """
        try:
            logger.info(
                f"Запуск TruffleHog {trufflehog_version} для сканирования секретов: {repo_path}"
            )
            findings = ScanProcessor._scan_with_trufflehog_brew(repo_path)

            # Обрабатываем результаты
            if findings:
                for finding in findings:
                    ScanProcessor._save_secret_finding(scan_request, finding)
                logger.info(f"Успешно сохранено {len(findings)} находок")
            else:
                # Если ничего не найдено, создаем запись об успешном сканировании без находок
                ScanResult.objects.create(
                    scan_request=scan_request,
                    status=False,
                    file_path="SYSTEM",
                    str_number=0,
                    bug_type="SECRETS",
                    description="Сканирование завершено. Секреты не найдены.",
                )
                logger.info("Сканирование завершено, секреты не найдены")

        except Exception as e:
            logger.error(f"Критическая ошибка при сканировании секретов: {e}")
            ScanResult.objects.create(
                scan_request=scan_request,
                status=False,
                file_path="SYSTEM",
                str_number=0,
                bug_type="SECRETS",
                error_message=f"Ошибка сканирования: {str(e)[:500]}",
            )

    @staticmethod
    def _scan_with_trufflehog_brew(repo_path):
        """
        Сканирование с помощью TruffleHog v3 из brew
        """
        command_variants = [
            ["trufflehog", "filesystem", repo_path, "--json"],
            # С отключенной верификацией
            ["trufflehog", "filesystem", repo_path, "--json", "--no-verification"],
            # С дополнительными опциями
            ["trufflehog", "filesystem", repo_path, "--json", "--only-verified=false"],
            # С включенной историей git
            [
                "trufflehog",
                "filesystem",
                repo_path,
                "--json",
                "--since-commit",
                "HEAD~100",
            ],
        ]

        for i, scan_args in enumerate(command_variants):
            logger.info(f"Попытка brew.{i + 1}: {' '.join(scan_args)}")

            try:
                result = subprocess.run(
                    scan_args,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    cwd=repo_path,
                )

                logger.info(
                    f"TruffleHog brew.{i + 1} завершился с кодом: {result.returncode}"
                )
                logger.info(f"Stdout длина: {len(result.stdout)}")
                logger.info(
                    f"Stderr: {result.stderr[:500] if result.stderr else 'None'}"
                )

                if result.returncode == 0 and result.stdout.strip():
                    findings = ScanProcessor._parse_trufflehog_output(result.stdout)
                    if findings:
                        logger.info(f"Найдено {len(findings)} валидных результатов")
                        return findings
                    else:
                        logger.info("Найдены результаты, но они пустые или невалидные")
                else:
                    logger.warning(f"Вариант brew.{i + 1} не сработал")

            except subprocess.TimeoutExpired:
                logger.error("TruffleHog превысил время выполнения")
                break
            except Exception as e:
                logger.warning(f"Ошибка в варианте brew.{i + 1}: {e}")
                continue

        return []

    @staticmethod
    def _parse_trufflehog_output(output):
        findings = []
        valid_lines = 0
        invalid_lines = 0

        for line in output.strip().split("\n"):
            if line.strip():
                try:
                    finding = json.loads(line)

                    # Проверяем, что это валидная находка
                    if isinstance(finding, dict):
                        # Для TruffleHog v3 ключи могут быть разными
                        detector_name = (
                            finding.get("DetectorName")
                            or finding.get("detectorName")
                            or finding.get("Detector")
                            or finding.get("detector")
                        )

                        if detector_name:
                            findings.append(finding)
                            valid_lines += 1
                        else:
                            invalid_lines += 1
                    else:
                        invalid_lines += 1

                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Не удалось распарсить JSON: {line[:100]}..., ошибка: {e}"
                    )
                    invalid_lines += 1
                    continue

        logger.info(
            f"Парсинг завершен: {valid_lines} валидных, {invalid_lines} невалидных строк"
        )
        return findings

    @staticmethod
    def _save_secret_finding(scan_request, finding):
        """
        Сохраняет найденный секрет в базу данных
        """
        try:
            file_path = (
                finding.get("Path")
                or finding.get("path")
                or finding.get("File")
                or finding.get("file")
                or "Unknown"
            )

            line_number = (
                finding.get("Line")
                or finding.get("line")
                or finding.get("LineNumber")
                or finding.get("lineNumber")
                or 1
            )

            secret_type = (
                finding.get("DetectorName")
                or finding.get("detectorName")
                or finding.get("Detector")
                or finding.get("detector")
                or "Unknown Secret"
            )

            confidence = (
                finding.get("Confidence")
                or finding.get("confidence")
                or finding.get("Certainty")
                or finding.get("certainty")
                or "medium"
            )

            raw = (
                finding.get("Raw")
                or finding.get("raw")
                or finding.get("Content")
                or finding.get("content")
                or ""
            )[:1000]

            # Создаем описание на основе типа секрета
            description_map = {
                "AWS": "AWS ключ доступа",
                "Generic Secret": "Общий секрет",
                "Private Key": "Приватный ключ",
                "API Key": "API ключ",
                "JWT": "JWT токен",
                "Password": "Пароль",
                "Connection String": "Строка подключения к БД",
                "GitHub": "GitHub токен",
                "Google": "Google API ключ",
                "Slack": "Slack токен",
                "Stripe": "Stripe ключ",
                "Environment Variables": "Переменные окружения",
                "Database Password": "Пароль базы данных",
            }

            readable_type = description_map.get(secret_type, secret_type)

            # Создаем запись результата
            ScanResult.objects.create(
                scan_request=scan_request,
                status=True,
                file_path=file_path,
                str_number=line_number,
                bug_type="SECRETS",
                secret_type=secret_type,
                confidence=confidence,
                raw_context=raw,
                description=f"Найден {readable_type} (уверенность: {confidence})",
            )

            logger.info(f"Сохранена находка: {file_path}:{line_number} - {secret_type}")

        except Exception as e:
            logger.error(f"Ошибка при сохранении finding: {e}")

    @staticmethod
    def _scan_dependencies(scan_request, repo_path):
        try:
            logger.info(f"Сканирование зависимостей для: {repo_path}")

            # Ищем файлы зависимостей
            dependency_files = []
            for root, dirs, files in os.walk(repo_path):
                # Игнорируем скрытые директории
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for file in files:
                    if file in [
                        "requirements.txt",
                        "package.json",
                        "pom.xml",
                        "build.gradle",
                        "composer.json",
                    ]:
                        full_path = os.path.join(root, file)
                        dependency_files.append(full_path)

            if dependency_files:
                for file_path in dependency_files[:5]:
                    rel_path = os.path.relpath(file_path, repo_path)
                    ScanResult.objects.create(
                        scan_request=scan_request,
                        status=True,
                        file_path=rel_path,
                        str_number=1,
                        bug_type="DEPENDENCIES",
                        description="Файл зависимостей найден",
                    )
            else:
                ScanResult.objects.create(
                    scan_request=scan_request,
                    status=False,
                    file_path="ROOT",
                    str_number=0,
                    bug_type="DEPENDENCIES",
                    description="Файлы зависимостей не найдены",
                )

        except Exception as e:
            logger.error(f"Ошибка при сканировании зависимостей: {e}")
            ScanResult.objects.create(
                scan_request=scan_request,
                status=False,
                file_path="SYSTEM",
                str_number=0,
                bug_type="DEPENDENCIES",
                error_message=str(e)[:500],
            )

    @staticmethod
    def start_scan_async(scan_request_id):
        """
        Запускает сканирование в отдельном потоке
        """
        thread = threading.Thread(
            target=ScanProcessor.process_scan, args=(scan_request_id,)
        )
        thread.daemon = True
        thread.start()
