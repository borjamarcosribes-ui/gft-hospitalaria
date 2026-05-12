import os

CIMA_BASE_URL = os.getenv("CIMA_BASE_URL", "https://cima.aemps.es/cima/rest")

BIFIMED_BASE_URL = os.getenv(
    "BIFIMED_BASE_URL",
    "https://www.sanidad.gob.es/profesionales/medicamentos.do",
)

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
