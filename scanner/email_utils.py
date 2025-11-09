from django.conf import settings
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)

class EmailNotifier:

    @staticmethod
    def send_scan_results_email(user_email, user_name, repository_url, scan_results, scan_request_id):
        """
        Отправляет email с результатами сканирования
        """
        try:
            # Подготавливаем данные для письма
            context = {
                'user_name': user_name,
                'repository_url': repository_url,
                'scan_results': scan_results,
                'scan_request_id': scan_request_id,
                'total_findings': len(scan_results),
                'high_confidence_findings': len([r for r in scan_results if r.confidence == 'high']),
                'secrets_found': len([r for r in scan_results if r.bug_type == 'SECRETS']),
                'dependencies_found': len([r for r in scan_results if r.bug_type == 'DEPENDENCIES']),
            }

            subject = f" Отчет о сканировании репозитория #{scan_request_id}"

            text_message = f"""
Здравствуйте, {user_name}!

Отчет о сканировании репозитория готов.

Репозиторий: {repository_url}
ID сканирования: #{scan_request_id}

Общие результаты:
- Всего находок: {context['total_findings']}
- С высокой уверенностью: {context['high_confidence_findings']}
- Секреты: {context['secrets_found']}
- Зависимости: {context['dependencies_found']}

Детали найденных уязвимостей:

"""

            for i, result in enumerate(scan_results, 1):
                status = "Найдено" if result.status else " Не найдено"
                confidence_badge = {
                    'high': ' ВЫСОКАЯ',
                    'medium': ' СРЕДНЯЯ',
                    'low': ' НИЗКАЯ'
                }.get(result.confidence, '⚪ НЕИЗВЕСТНО')

                text_message += f"""
{i}. {status}
   Файл: {result.file_path}
   Строка: {result.str_number}
   Тип: {result.get_bug_type_display()}
   Уверенность: {confidence_badge}
   Описание: {result.description or 'Нет описания'}

"""

            text_message += """
С уважением,
Сервис анализа безопасности GitHub репозиториев

Примечание: Это автоматическое уведомление. Пожалуйста, не отвечайте на это письмо.
"""

            # Отправляем email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user_email],
                fail_silently=False,
            )

            logger.info(f"Email уведомление отправлено пользователю {user_email} для сканирования {scan_request_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка при отправке email уведомления: {e}")
            return False

    @staticmethod
    def send_scan_completion_notification(scan_request):
        """
        Отправляет уведомление о завершении сканирования
        """
        try:
            user = scan_request.user
            scan_results = scan_request.scan_results.all()

            # Отправляем email пользователю
            EmailNotifier.send_scan_results_email(
                user_email=user.email,
                user_name=user.username,
                repository_url=scan_request.repository_url,
                scan_results=scan_results,
                scan_request_id=scan_request.id
            )

            # Дополнительно можно отправлять уведомление администратору
            if hasattr(settings, 'ADMIN_EMAIL') and settings.ADMIN_EMAIL:
                EmailNotifier._send_admin_notification(scan_request, scan_results)

        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о завершении сканирования: {e}")

    @staticmethod
    def _send_admin_notification(scan_request, scan_results):
        """
        Отправляет уведомление администратору
        """
        try:
            subject = f" Сканирование #{scan_request.id} завершено"

            message = f"""
Администратору,

Сканирование репозитория завершено.

Детали:
- Пользователь: {scan_request.user.username}
- Репозиторий: {scan_request.repository_url}
- ID сканирования: #{scan_request.id}
- Тип сканирования: {scan_request.get_scan_type_display()}
- Глубина: {scan_request.get_scan_depth_display()}
- Найдено уязвимостей: {len(scan_results)}

Время: {scan_request.updated_at.strftime('%Y-%m-%d %H:%M:%S')}
"""

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL],
                fail_silently=True,
            )

            logger.info(f"Уведомление администратору отправлено для сканирования {scan_request.id}")

        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления администратору: {e}")

    @staticmethod
    def send_scan_error_notification(scan_request, error_message):
        """
        Отправляет уведомление об ошибке сканирования
        """
        try:
            subject = f" Ошибка сканирования репозитория #{scan_request.id}"

            message = f"""
Здравствуйте, {scan_request.user.username}!

К сожалению, при сканировании вашего репозитория произошла ошибка.

Репозиторий: {scan_request.repository_url}
ID сканирования: #{scan_request.id}

Ошибка: {error_message}

Пожалуйста, попробуйте запустить сканирование еще раз или обратитесь в поддержку.

С уважением,
Сервис анализа безопасности GitHub репозиториев
"""

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[scan_request.user.email],
                fail_silently=False,
            )

            logger.info(f"Уведомление об ошибке отправлено пользователю {scan_request.user.email}")

        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об ошибке: {e}")