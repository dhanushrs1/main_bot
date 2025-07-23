FROM python:3.11

WORKDIR /main-bot

COPY . /main-bot

RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
