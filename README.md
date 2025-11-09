Команда запуска:docker compose up --build
После чего применяем миграции базы данных docker compose exec osint python manage.py makemigrations
и docker compose exec osint python manage.py migrate