import os
import tempfile
import shutil
import requests
import zipfile
import io
from git import Repo
from git.exc import GitCommandError
import logging

logger = logging.getLogger(__name__)


def download_github_repository(repo_url, download_path=None, include_history=False):
    try:
        logger.info(f"Начало скачивания: {repo_url}")

        repo_url = repo_url.strip().split("?")[0].split("#")[0]

        if not repo_url.startswith("https://github.com/"):
            logger.error(f"Неверный GitHub URL: {repo_url}")
            return None

        if download_path is None:
            download_path = tempfile.mkdtemp(prefix="github_repo_")
            logger.info(f"Создана временная директория: {download_path}")

        git_url = repo_url if repo_url.endswith(".git") else repo_url + ".git"

        logger.info(f"Клонирование: {git_url} -> {download_path}")

        try:
            if include_history:
                repo = Repo.clone_from(git_url, download_path)
                logger.info("Полное клонирование успешно")
            else:
                repo = Repo.clone_from(git_url, download_path, depth=1)
                logger.info("Поверхностное клонирование успешно")

            if os.path.exists(download_path) and os.listdir(download_path):
                logger.info(f"Репо успешно скачан: {download_path}")
                return download_path
            else:
                logger.error("Директория репозитория пуста")
                return None

        except GitCommandError as e:
            logger.error(f"Ошибка Git: {e}")
            return download_github_repository_zip_simple(repo_url, download_path)

    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        return None


def download_github_repository_zip_simple(repo_url, download_path):
    try:
        logger.info("Попытка скачать через ZIP...")

        # Извлекаем owner/repo из URL
        parts = repo_url.rstrip("/").split("/")
        if "github.com" not in parts:
            return None

        github_index = parts.index("github.com")
        owner = parts[github_index + 1]
        repo_name = parts[github_index + 2].replace(".git", "")

        logger.info(f"Owner: {owner}, Repo: {repo_name}")

        # Пробуем основные ветки
        for branch in ["main", "master"]:
            zip_url = f"https://github.com/{owner}/{repo_name}/archive/refs/heads/{branch}.zip"
            logger.info(f"Попытка скачать: {zip_url}")

            try:
                response = requests.get(zip_url, timeout=30)
                if response.status_code == 200:
                    # Распаковываем ZIP
                    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                        zip_file.extractall(download_path)

                    logger.info(f"ZIP успешно скачан и распакован в: {download_path}")
                    return download_path

            except Exception as e:
                logger.warning(f"Не удалось скачать ветку {branch}: {e}")
                continue

        logger.error("Не удалось скачать ни одну ветку")
        return None

    except Exception as e:
        logger.error(f"Ошибка при скачивании ZIP: {e}")
        return None


def cleanup_repository(path):
    try:
        if path and os.path.exists(path):
            if any(
                prefix in path
                for prefix in ["github_repo_", "/tmp/", tempfile.gettempdir()]
            ):
                shutil.rmtree(path)
                logger.info(f"Репо удален: {path}")
            else:
                logger.warning(f"Попытка удалить небезопасный путь: {path}")
    except Exception as e:
        logger.error(f"Ошибка при удалении репо {path}: {e}")


def get_repository_info(repo_path):
    try:
        if not os.path.exists(os.path.join(repo_path, ".git")):
            logger.warning(f"Директория {repo_path} не является Git репозиторием")
            return {"is_git_repo": False, "file_count": count_files(repo_path)}

        repo = Repo(repo_path)

        commits = list(repo.iter_commits())
        active_branch = None
        try:
            active_branch = repo.active_branch.name
        except:
            active_branch = "detached"

        info = {
            "is_git_repo": True,
            "branch": active_branch,
            "commit_count": len(commits),
            "latest_commit": commits[0].hexsha[:8] if commits else None,
            "author": commits[0].author.name if commits else None,
            "message": commits[0].message.split("\n")[0]
            if commits
            else None,  # Первая строка сообщения
            "file_count": count_files(repo_path),
            "repo_size": get_directory_size(repo_path),
        }

        logger.info(f"Информация о репо: {info}")
        return info

    except Exception as e:
        logger.error(f"Ошибка при получении информации о репо: {e}")
        return None


def count_files(directory):
    try:
        file_count = 0
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            file_count += len(files)
        return file_count
    except Exception as e:
        logger.error(f"Ошибка при подсчете файлов: {e}")
        return 0


def get_directory_size(directory):
    try:
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(directory):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    continue
        return round(total_size / (1024 * 1024), 2)
    except Exception as e:
        logger.error(f"Ошибка при вычислении размера директории: {e}")
        return 0


def validate_github_url(url):
    if not url:
        return False, "URL не может быть пустым"

    url = url.strip()

    if not url.startswith("https://github.com/"):
        return False, "Должен быть HTTPS URL GitHub репозитория"

    parts = url.rstrip("/").split("/")
    if len(parts) < 5 or parts[2] != "github.com":
        return False, "Неверный формат GitHub URL"

    owner = parts[3]
    repo = parts[4]

    if not owner or not repo:
        return False, "Не удалось извлечь владельца и имя репозитория"

    # Проверяем допустимые символы
    import re

    if not re.match(r"^[a-zA-Z0-9_.-]+$", owner):
        return False, "Недопустимые символы в имени владельца"

    if not re.match(r"^[a-zA-Z0-9_.-]+$", repo):
        return False, "Недопустимые символы в имени репозитория"

    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        response = requests.get(api_url, timeout=10)

        if response.status_code == 404:
            return False, "Репозиторий не найден"
        elif response.status_code == 403:
            # Rate limit или приватный репозиторий
            return True, "Отсутствует доступ к репозиторию"
        elif response.status_code == 200:
            return True, "Репозиторий существует и доступен"
        else:
            return True, f"Возникла ошибка (статус: {response.status_code})"

    except requests.RequestException:
        return True, "проверка репозитория недоступна"
