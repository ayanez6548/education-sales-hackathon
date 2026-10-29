"""Fictional demo catalog. Replace these records before any live commercial use."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CatalogCourse:
    slug: str
    name: str
    description: str
    contents: str
    requirements: str
    modality: str
    duration: str
    schedule: str
    price_amount: int
    price_currency: str = "USD"
    authorized_link: str | None = None
    search_aliases: list[str] = field(default_factory=list)


DEMO_COURSES: list[CatalogCourse] = [
    CatalogCourse(
        slug="excel-laboral",
        name="Excel laboral",
        description=(
            "Curso ficticio de demostración para organizar datos, tablas dinámicas y reportes "
            "de uso cotidiano en oficina."
        ),
        contents="Tablas, fórmulas de búsqueda, gráficos y tablas dinámicas introductorias.",
        requirements="Computadora con hoja de cálculo. No se exige experiencia previa.",
        modality="Virtual en vivo",
        duration="24 horas académicas",
        schedule="Martes y jueves, 19:00 a 21:00 (America/Guayaquil)",
        price_amount=120,
        search_aliases=["excel", "exel", "excell", "hoja de calculo", "office"],
    ),
    CatalogCourse(
        slug="python-datos",
        name="Python para datos",
        description=(
            "Curso ficticio de demostración para iniciar análisis de datos con Python, "
            "pandas y visualizaciones básicas."
        ),
        contents="Sintaxis, pandas, limpieza de datos y gráficos introductorios.",
        requirements="Lógica básica. Se entrega entorno de prácticas guiado.",
        modality="Híbrida",
        duration="32 horas académicas",
        schedule="Sábados, 09:00 a 13:00 (America/Guayaquil)",
        price_amount=180,
        search_aliases=["python", "phyton", "piton", "pyton", "datos", "pandas"],
    ),
    CatalogCourse(
        slug="ingles-negocios",
        name="Inglés para negocios",
        description=(
            "Curso ficticio de demostración enfocado en reuniones, correos y presentaciones "
            "en un entorno laboral."
        ),
        contents="Correo profesional, llamadas, vocabulario comercial y simulaciones.",
        requirements="Nivel A2 o equivalente autodeclarado.",
        modality="Virtual en vivo",
        duration="40 horas académicas",
        schedule="Lunes y miércoles, 18:30 a 20:30 (America/Guayaquil)",
        price_amount=160,
        search_aliases=["ingles", "english", "inglés", "negocios"],
    ),
    CatalogCourse(
        slug="atencion-cliente",
        name="Atención al cliente",
        description=(
            "Curso ficticio de demostración sobre escucha, reclamos y calidad de servicio "
            "en canales digitales y presenciales."
        ),
        contents="Protocolos de servicio, manejo de reclamos y seguimiento.",
        requirements="Ninguno. Pensado para personal en contacto con usuarios.",
        modality="Presencial",
        duration="16 horas académicas",
        schedule="Viernes, 08:00 a 12:00 (America/Guayaquil)",
        price_amount=90,
        search_aliases=["cliente", "servicio", "atencion", "atención"],
    ),
    CatalogCourse(
        slug="marketing-digital",
        name="Marketing digital para pymes",
        description=(
            "Curso ficticio de demostración para planificar contenidos, campañas básicas "
            "y medición de resultados en redes."
        ),
        contents="Embudo simple, contenidos, métricas básicas y calendario editorial.",
        requirements="Manejo básico de redes sociales personales o de un negocio.",
        modality="Virtual en vivo",
        duration="20 horas académicas",
        schedule="Jueves, 18:00 a 21:00 (America/Guayaquil)",
        price_amount=140,
        search_aliases=["marketing", "mkt", "redes", "pymes", "publicidad"],
    ),
]


def normalize(text: str) -> str:
    replacements = str.maketrans(
        "áéíóúüñÁÉÍÓÚÜÑ",
        "aeiouunAEIOUUN",
    )
    return " ".join(text.translate(replacements).lower().split())


def match_courses(query: str, courses: list[CatalogCourse] | None = None) -> list[CatalogCourse]:
    source = courses or DEMO_COURSES
    blob = normalize(query)
    ranked: list[tuple[int, CatalogCourse]] = []
    for course in source:
        haystack = normalize(
            " ".join([course.slug, course.name, course.description, *course.search_aliases])
        )
        score = 0
        if course.slug.replace("-", " ") in blob or course.slug in blob:
            score += 5
        for alias in course.search_aliases:
            if normalize(alias) in blob:
                score += 3
        for token in normalize(course.name).split():
            if len(token) > 3 and token in blob:
                score += 1
        if score:
            ranked.append((score, course))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [course for _, course in ranked]
