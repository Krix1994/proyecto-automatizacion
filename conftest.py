"""
conftest.py
Fixtures compartidas para todas las pruebas de regresión de Dent-OS.

pytest carga este archivo automáticamente (no hay que importarlo).
Cualquier fixture definida aquí queda disponible para TODOS los
archivos test_*.py de la misma carpeta (y subcarpetas).
"""

import os
import re
import pytest
from dotenv import load_dotenv
from playwright.sync_api import Page, expect

# Carga las variables definidas en el archivo .env (que NO se sube a
# GitHub, ver .gitignore) hacia el entorno, para que os.environ.get(...)
# las encuentre más abajo.
load_dotenv()

USUARIO = os.environ["DENTOS_USUARIO"]
PASSWORD = os.environ["DENTOS_PASSWORD"]
SUCURSAL = os.environ.get("DENTOS_SUCURSAL", "Bucaramanga")

URL_LOGIN = "https://release.dentos.co/auth/login"

# Paciente de prueba usado por defecto en la mayoría de los tests.
NOMBRE_PACIENTE = "ADRIANA CATHERINE"

# Paciente alterno, con menos historial de pruebas acumulado. Útil para
# pruebas que empiezan a fallar en NOMBRE_PACIENTE por saturación de
# datos (muchos planes/anticipos creados de tanto correr las pruebas).
NOMBRE_PACIENTE_ALT = "CARMEN CAUSEL MESTRA"


@pytest.fixture
def pagina_logueada(page: Page) -> Page:
    """
    Hace login en Dent-OS y deja la página lista para que cada test
    continúe desde el dashboard, sin tener que repetir estos pasos
    en cada archivo.

    Uso en un test:
        def test_algo(pagina_logueada):
            pagina_logueada.get_by_title("Pacientes")...
    """
    page.set_default_timeout(60000)  # 60s: el sitio a veces tarda en cargar

    page.goto(URL_LOGIN)
    page.get_by_role("textbox", name="Usuario").click()
    page.get_by_role("textbox", name="Usuario").fill(USUARIO)
    page.get_by_role("textbox", name="Contraseña").click()
    page.get_by_role("textbox", name="Contraseña").fill(PASSWORD)
    page.locator("#id_sucursal").select_option(label=SUCURSAL)
    page.get_by_role("button", name="Ingresar").click()

    return page


def buscar_y_abrir_paciente(pagina_logueada: Page, nombre_paciente: str) -> Page:
    """
    Busca un paciente por nombre en el "Listado de Pacientes" y hace
    clic en el resultado para abrir su ficha. Función reutilizable para
    no repetir esta lógica en cada fixture de paciente.
    """
    pagina_logueada.get_by_title("Pacientes").get_by_role("link").click()

    # Escribir el nombre en la caja de "Búsqueda Simple" para filtrar
    # la lista (815 pacientes en total, por eso hay que buscar primero).
    #
    # NOTA: se usa el primer <input type="text"> visible en la página en
    # lugar de un ID o placeholder específico, porque los IDs que genera
    # ExtJS cambian entre sesiones y el placeholder no se pudo confirmar
    # con certeza. Esta caja es el primer campo de texto de la pantalla
    # "Listado de Pacientes", así que debería ser estable.
    caja_busqueda = pagina_logueada.locator("input[type='text']").first
    caja_busqueda.click()
    caja_busqueda.press_sequentially(nombre_paciente, delay=80)
    pagina_logueada.wait_for_timeout(1000)

    resultado = pagina_logueada.get_by_text(nombre_paciente)
    expect(resultado).to_be_visible(timeout=10000)
    resultado.click()

    return pagina_logueada


@pytest.fixture
def pagina_con_paciente(pagina_logueada: Page) -> Page:
    """
    Extiende 'pagina_logueada': además de loguear, abre el paciente
    de prueba por defecto (NOMBRE_PACIENTE). Útil para los tests que
    empiezan siempre buscando el mismo paciente.

    Si un test necesita OTRO paciente, no uses esta fixture: usa
    'pagina_logueada' y busca el paciente que corresponda dentro del
    propio test.
    """
    return buscar_y_abrir_paciente(pagina_logueada, NOMBRE_PACIENTE)


@pytest.fixture
def pagina_con_paciente_alt(pagina_logueada: Page) -> Page:
    """
    Igual que 'pagina_con_paciente', pero abre el paciente alterno
    (NOMBRE_PACIENTE_ALT), con menos historial de pruebas acumulado.
    """
    return buscar_y_abrir_paciente(pagina_logueada, NOMBRE_PACIENTE_ALT)


def abrir_combo_ext(page: Page, ids_conocidos: list, texto_opcion: str) -> None:
    """
    Abre un combo/desplegable de ExtJS y hace clic en la opción indicada.

    Los IDs autogenerados de ExtJS (#ext-gen89, #ext-gen90, etc.) cambian
    ligeramente entre sesiones o cargas de página. En lugar de depender de
    un único ID fijo, esta función prueba varios IDs cercanos a los ya
    conocidos hasta encontrar el que realmente abre el combo (confirmado
    porque después aparece 'texto_opcion' en pantalla), y hace clic ahí.

    ids_conocidos: lista de IDs numéricos que en algún momento funcionaron
    para este mismo combo (ej. [89, 90, 114]). Se probará un rango
    alrededor de cada uno.
    """
    for base in ids_conocidos:
        for delta in range(-15, 16):
            candidato = page.locator(f"#ext-gen{base + delta}")
            if candidato.count() == 0:
                continue
            try:
                candidato.click(timeout=800)
                opcion = page.get_by_text(texto_opcion)
                opcion.wait_for(state="visible", timeout=800)
                opcion.click()
                return
            except Exception:
                continue

    raise AssertionError(
        f"No se pudo abrir el combo ni encontrar la opción '{texto_opcion}' "
        f"probando IDs cercanos a {ids_conocidos}. Puede que el ID haya "
        f"cambiado más de lo esperado: vuelve a grabar este paso con "
        f"'playwright codegen' y actualiza 'ids_conocidos'."
    )
