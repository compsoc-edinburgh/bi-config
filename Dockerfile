FROM python:3

RUN apt-get update -y && \
    apt-get install -y libldap2-dev libsasl2-dev
RUN pip install pipenv

WORKDIR /code
ADD ./Pipfile.lock /code/Pipfile.lock
ADD ./Pipfile /code/Pipfile

RUN pipenv install --system --deploy

ADD . /code

EXPOSE 9991

CMD ["gunicorn", "-b", "0.0.0.0:9991", "app:app"]
