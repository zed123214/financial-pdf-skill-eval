FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY financial-pdf-skill-eval-framework/requirements.txt /tmp/requirements.txt
COPY financial-pdf-skill-eval-framework/requirements-dashboard.txt /tmp/requirements-dashboard.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt -r /tmp/requirements-dashboard.txt

COPY . /app

WORKDIR /app/financial-pdf-skill-eval-framework
RUN python run.py --build-dashboard-bundle

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "dashboard/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
