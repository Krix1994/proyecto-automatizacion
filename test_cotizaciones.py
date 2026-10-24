"""
Pruebas de regresión: Cotizaciones - Dent-OS
Casos cubiertos:
  #11  Crear cotización
  #12  Imprimir cotización
  #13  Convertir cotización a Plan de Tratamiento (PTT)
  #14  Modificar cotización
  #15  Eliminar cotización
"""

import re
from contextlib import contextmanager

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect

# Procedimiento que lleva la cotización que crea cada prueba, y el diente.
PROCEDIMIENTO = "NUCLEO ADHESIVO"
DIENTE = "23"

# Segundos (en milisegundos) que se deja abierto el comprobante de impresión
# para poder verlo antes de cerrarlo. Se puede bajar para acelerar la prueba.
PAUSA_COMPROBANTE_MS = 4000

# Pausa final, al terminar cada prueba, para ver cómo queda la pantalla antes
# de que se cierre el navegador. Poner 0 para correr más rápido.
PAUSA_FINAL_MS = 3000

# Valor que se escribe al modificar la cotización.
NUEVO_VALOR = "1000"

# Cada cotización de la lista tiene cuatro botones cuyo id lleva su número:
#   imp_NNNN = imprimir, edt_NNNN = modificar, del_NNNN = eliminar,
#   cnv_NNNN = convertir a plan de tratamiento.
# Así cada prueba identifica SU cotización sin depender de datos viejos.


def _aviso_en_pantalla(page: Page) -> str:
    """
    Texto de la notificación que muestra la aplicación, o "" si no hay
    ninguna. Se lee con un tiempo máximo de 1 s: sin él, si el elemento no
    existe Playwright esperaba su tiempo máximo (30 a 60 s) antes de rendirse.
    """
    try:
        return " ".join(page.locator("#msg-div").inner_text(timeout=1000).split())
    except Exception:
        return ""


def _esperar_vuelta_a_la_lista(page: Page, espera_ms: int = 15000) -> bool:
    """
    Espera a que la aplicación vuelva sola a la lista de cotizaciones después
    de guardar (la dirección cambia a /tratamiento/index/index/...). Devuelve
    True en cuanto ocurre, sin esperar de más; False si no ocurre a tiempo.
    """
    try:
        page.wait_for_url(re.compile(r"/tratamiento/index/index/"), timeout=espera_ms)
        return True
    except PlaywrightError:
        return False


def _paso(texto: str) -> None:
    """Escribe en la terminal el paso que está haciendo la prueba (se ve en
    vivo al correr con -s y sin guardar el resultado en un archivo)."""
    print(f"\nPASO: {texto}", flush=True)


def _resaltar(page: Page, campo, texto: str) -> None:
    """Resalta un campo en el navegador y lo deja a la vista unos segundos,
    para poder ver cuál es."""
    _paso(f"{texto} (campo resaltado; se deja {PAUSA_FINAL_MS // 1000} s para verlo)")
    try:
        campo.highlight()
    except Exception:
        pass
    page.wait_for_timeout(PAUSA_FINAL_MS)


def _mapa_controles(page: Page) -> list:
    """Controles visibles de la pantalla (id, nombre, clase, texto), para
    ver sus nombres reales cuando algo falla."""
    return page.evaluate(
        """() => Array.from(document.querySelectorAll(
            'input, textarea, button, img[id], a[id], table.x-btn'))
          .filter(e => e.offsetParent !== null)
          .map(e => `${e.tagName.toLowerCase()} id=${e.id} name=${e.name || ''}`
            + ` class=${(e.className || '').toString().slice(0, 40)}`
            + ` texto=${(e.innerText || e.value || e.title || '').toString().trim().slice(0, 30)}`)
          .slice(0, 80)"""
    )


@contextmanager
def _mapa_si_falla(page: Page):
    """Si algo falla, imprime los controles de la pantalla y vuelve a fallar."""
    try:
        yield
    except Exception:
        # Si la pantalla estaba cambiando, se espera a que termine de cargar
        # para que la lista de controles sea la real.
        try:
            page.wait_for_load_state("load", timeout=10000)
            page.wait_for_timeout(2000)
        except Exception:
            pass
        print("\nCOTIZACION: ERROR. Controles visibles en la pantalla:")
        try:
            print(f"    url = {page.url!r}")
            for linea in _mapa_controles(page):
                print("   ", linea)
        except Exception:
            pass
        raise


def _ids_con_prefijo(page: Page, prefijo: str) -> set:
    """
    Números de los elementos de la pantalla cuyo id es "<prefijo>_NNNN":
    "imp" son las cotizaciones y "deltrat" los planes de tratamiento. Si la
    página cambia de pantalla justo mientras se lee ("Execution context was
    destroyed"), se espera a que cargue y se vuelve a intentar.
    """
    for intento in range(6):
        try:
            ids = page.locator(f'[id^="{prefijo}_"]').evaluate_all(
                "els => els.map(e => e.id)"
            )
            return {int(i.split("_")[1]) for i in ids if i.split("_")[1].isdigit()}
        except PlaywrightError as error:
            if "context was destroyed" not in str(error) or intento == 5:
                raise
            page.wait_for_timeout(1000)
            page.wait_for_load_state("load")
    return set()


def _ids_cotizaciones(page: Page) -> set:
    """Números de las cotizaciones que muestra la lista (por sus botones imp_)."""
    return _ids_con_prefijo(page, "imp")


def _ids_estables(page: Page) -> set:
    """
    Lee los números de cotización hasta que no cambian durante 3 lecturas
    seguidas. La lista se carga unos instantes después de abrir la pantalla y
    a veces tarda: una lista VACÍA solo se acepta si sigue vacía después de
    unos 12 segundos. Si se tomara una lista vacía por buena, todas las
    cotizaciones que ya existían parecerían "nuevas".
    """
    anterior = _ids_cotizaciones(page)
    iguales = 0
    for vuelta in range(1, 31):
        page.wait_for_timeout(1000)
        actual = _ids_cotizaciones(page)
        if actual == anterior and (actual or vuelta >= 12):
            iguales += 1
            if iguales >= 3:
                return actual
        else:
            iguales = 0
        anterior = actual
    return anterior


def _esperar_cotizacion_nueva(page: Page, base: set) -> int:
    """Espera a que aparezca UNA cotización que no estaba en `base` y
    devuelve su número."""
    nuevos: set = set()
    for _ in range(40):
        nuevos = _ids_cotizaciones(page) - base
        if nuevos:
            break
        page.wait_for_timeout(500)
    assert len(nuevos) == 1, (
        f"Se esperaba una cotización nueva y hay {len(nuevos)}: {sorted(nuevos)} "
        f"(la lista de partida tenía {len(base)}; si tenía 0, la lista no había "
        f"terminado de cargar)"
    )
    return nuevos.pop()


def _crear_cotizacion(page: Page) -> tuple:
    """
    Crea una cotización con el procedimiento PROCEDIMIENTO y devuelve su
    número y los números que había antes (la "base").
    """
    _paso("abriendo el plan de tratamiento de la paciente")
    page.locator("#pt").click()
    # La pantalla del plan puede tardar en cargar o cambiar una vez más:
    # se espera a que termine antes de leer la lista.
    page.wait_for_load_state("load")
    boton_nueva = page.get_by_role("button", name="Nueva cotización (Particular)")
    expect(boton_nueva).to_be_visible(timeout=20000)
    page.wait_for_timeout(1500)
    page.wait_for_load_state("load")
    print(f"\nCOTIZACION: pantalla de cotizaciones = {page.url!r}")
    base = _ids_estables(page)

    _paso('pulsando "Nueva cotización (Particular)"')
    boton_nueva.click()

    # Puede salir una ventana con "Aceptar" antes de la pantalla de la
    # cotización: se espera lo primero que aparezca (ventana o campo).
    aceptar = page.get_by_role("button", name="Aceptar", exact=True)
    campo_procedimiento = page.locator("#cb_proc")
    aceptar.or_(campo_procedimiento).first.wait_for(state="visible", timeout=30000)
    if aceptar.is_visible():
        aceptar.click()

    _paso(f"eligiendo el procedimiento {PROCEDIMIENTO} y el diente {DIENTE}")
    campo_procedimiento.click()
    campo_procedimiento.fill("nucleo")
    # Se fuerza el evento 'keyup' que espera el filtro en vivo de ExtJS.
    campo_procedimiento.press("Backspace")
    campo_procedimiento.type("o", delay=100)
    page.wait_for_timeout(1000)
    opcion = (
        page.locator(".x-combo-list-item:visible")
        .filter(has_text=re.compile(rf"^\s*{re.escape(PROCEDIMIENTO)}\s*$"))
        .first
    )
    expect(opcion).to_be_visible(timeout=10000)
    opcion.click()

    # Controles tal como se grabaron (ids de ExtJS), con el nombre del campo
    # y la clase del botón como primera opción cuando existen.
    dientes = page.locator('input[name="tf_dientes"], #ext-comp-1005').first
    dientes.click()
    dientes.fill(DIENTE)
    page.locator("button.btn_add, #ext-gen36").first.click()
    _paso("guardando la cotización nueva")
    page.locator("#ext-gen56").click()

    numero = _esperar_cotizacion_nueva(page, base)
    print(f"\nCOTIZACION: cotización nueva = {numero}")
    return numero, base


def _eliminar_cotizacion(page: Page, numero: int) -> None:
    """Elimina la cotización y confirma que desapareció de la lista."""
    _paso(f"borrando la cotización {numero}")
    page.locator(f"#del_{numero}").click()
    page.get_by_role("button", name="Si", exact=True).click()
    expect(page.locator(f"#del_{numero}")).to_have_count(0, timeout=20000)


@contextmanager
def _cotizacion_nueva(page: Page):
    """
    Crea una cotización para la prueba y, al terminar, borra las que quedaron
    de ella (puede que modificarla le cambie el número) para no llenar el
    ambiente de cotizaciones de prueba.
    """
    numero, base = _crear_cotizacion(page)
    url_lista = page.url  # la lista de cotizaciones del paciente
    try:
        yield numero, base
    finally:
        try:
            # Si la prueba terminó en otra pantalla (por ejemplo la de edición),
            # se vuelve a la lista para poder borrar lo que quedó.
            if page.url != url_lista:
                page.goto(url_lista)
                page.wait_for_load_state("load")
            for sobrante in sorted(_ids_cotizaciones(page) - base):
                _eliminar_cotizacion(page, sobrante)
        except Exception as error:
            print(f"COTIZACION: ADVERTENCIA - no se pudo limpiar la cotización: {error}")
        _paso(f"limpieza terminada: se deja la pantalla {PAUSA_FINAL_MS // 1000} s para verla")
        page.wait_for_timeout(PAUSA_FINAL_MS)


def _texto_fila(page: Page, numero: int) -> str:
    """Texto de la fila de la lista que corresponde a la cotización."""
    fila = page.locator(f"#imp_{numero}").locator("xpath=ancestor::tr[1]")
    return " ".join(fila.inner_text().split())


def _entero_de(valor: str) -> int:
    """Número entero de un campo: "1000", "1,000", "1.000" y "1000.00" dan 1000."""
    sin_decimales = re.sub(r"[.,]\d{1,2}$", "", valor.strip())
    digitos = re.sub(r"\D", "", sin_decimales)
    assert digitos, f"No se encontró un número en: {valor!r}"
    return int(digitos)


def _esperar_fila_modificada(page: Page, base: set, fila_antes: str) -> tuple:
    """
    Espera (hasta unos 20 s) a que la lista muestre la cotización modificada,
    que puede conservar su número o quedar con uno nuevo. Devuelve el número,
    el texto de su fila y los números nuevos que vio. La espera termina en
    cuanto la fila es distinta a `fila_antes`.
    """
    actual, fila, nuevos = None, "", []
    for _ in range(40):
        try:
            nuevos = sorted(_ids_cotizaciones(page) - base)
            if len(nuevos) == 1:
                actual = nuevos[0]
                fila = _texto_fila(page, actual)
                if fila != fila_antes:
                    break
        except PlaywrightError:
            pass  # la pantalla estaba cambiando; se vuelve a intentar
        page.wait_for_timeout(500)
    return actual, fila, nuevos


def test_crear_cotizacion(pagina_con_paciente: Page):
    """
    #11 - En el plan de tto del paciente, sección de cotización,
    crear y guardar con datos.

    Crea una cotización con el procedimiento NUCLEO ADHESIVO (diente 23) y
    verifica que aparezca en la lista con sus botones. Al terminar la borra.
    """
    page = pagina_con_paciente

    with _mapa_si_falla(page), _cotizacion_nueva(page) as (numero, _base):
        fila = _texto_fila(page, numero)
        print(f"COTIZACION: fila creada = {fila!r}")
        for prefijo in ("imp", "edt", "del", "cnv"):
            expect(page.locator(f"#{prefijo}_{numero}")).to_have_count(1)


def test_imprimir_cotizacion(pagina_con_paciente: Page):
    """
    #12 - Botón de imprimir sobre la cotización creada.

    Crea su propia cotización, pulsa imprimir y verifica que se abra el
    comprobante en una ventana nueva. Al terminar borra la cotización.
    """
    page = pagina_con_paciente

    with _mapa_si_falla(page), _cotizacion_nueva(page) as (numero, _base):
        _paso("pulsando imprimir")
        with page.expect_popup() as popup_info:
            page.locator(f"#imp_{numero}").click()
        comprobante = popup_info.value
        comprobante.wait_for_load_state()
        url = comprobante.url
        _paso(f"comprobante abierto: se deja {PAUSA_COMPROBANTE_MS // 1000} s para verlo")
        # Se deja abierto unos segundos, al frente, para poder verlo.
        comprobante.bring_to_front()
        comprobante.wait_for_timeout(PAUSA_COMPROBANTE_MS)
        comprobante.close()
        print(f"COTIZACION: comprobante = {url!r}")
        assert url and url != "about:blank", (
            f"El comprobante no cargó una URL válida: {url!r}"
        )


def test_convertir_cotizacion_a_ptt(pagina_con_paciente: Page):
    """
    #13 - En el listado de cotizaciones, convertir la cotización
    a Plan de Tratamiento.

    Crea su propia cotización, pulsa convertir y confirma con "Si". Verifica
    tres cosas: que la aplicación avise "La cotización ha sido convertida
    correctamente", que la cotización ya no tenga el botón de convertir y que
    aparezca UN plan de tratamiento nuevo en la lista de planes del paciente.
    OJO: convertir crea un plan de tratamiento de verdad, que queda en el
    ambiente en cada corrida.
    """
    page = pagina_con_paciente

    with _mapa_si_falla(page), _cotizacion_nueva(page) as (numero, _base):
        url_lista = page.url
        planes_antes = _ids_con_prefijo(page, "deltrat")
        print(f"\nCOTIZACION: planes antes de convertir = {len(planes_antes)}")

        _paso("pulsando convertir y confirmando con Si")
        page.locator(f"#cnv_{numero}").click()
        page.get_by_role("button", name="Si", exact=True).click()

        # La aplicación avisa con una notificación y la cotización deja de
        # poder convertirse otra vez.
        expect(page.locator("#msg-div")).to_contain_text(
            "convertida correctamente", timeout=20000
        )
        expect(page.locator(f"#cnv_{numero}")).to_have_count(0, timeout=20000)

        _paso("comprobando que apareció un plan de tratamiento nuevo")
        # Se recarga la lista y debe aparecer UN plan nuevo.
        page.goto(url_lista)
        page.wait_for_load_state("load")
        nuevos: set = set()
        for _ in range(40):
            nuevos = _ids_con_prefijo(page, "deltrat") - planes_antes
            if nuevos:
                break
            page.wait_for_timeout(500)
        print(f"COTIZACION: planes nuevos tras convertir = {sorted(nuevos)}")
        assert len(nuevos) == 1, (
            f"Después de convertir se esperaba un plan de tratamiento nuevo y "
            f"hay {len(nuevos)}: {sorted(nuevos)}"
        )


def test_modificar_cotizacion(pagina_con_paciente: Page):
    """
    #14 - En el listado de cotizaciones, modificar la cotización.

    Crea su propia cotización, la modifica (escribe NUEVO_VALOR en el campo
    grabado), guarda, vuelve a abrir la cotización y verifica que el campo
    conserve el valor escrito. Al editar, la cotización puede quedar con otro
    número, por eso se busca la que no estaba antes. Al terminar borra lo
    que quede. No se compara el texto de la fila de la lista porque su
    columna de procedimientos se llena unos instantes después de la fila.
    """
    page = pagina_con_paciente

    with _mapa_si_falla(page), _cotizacion_nueva(page) as (numero, base):
        url_lista = page.url

        _paso(f"abriendo la pantalla de edición de la cotización {numero}")
        page.locator(f"#edt_{numero}").click()
        campo = page.locator("#ext-comp-1014")
        expect(campo).to_be_visible(timeout=20000)
        print(f"\nCOTIZACION: valor del campo antes = {campo.input_value()!r}")
        _resaltar(page, campo, f"este es el campo que se va a editar y ahora vale {campo.input_value()!r}")

        _paso(f"escribiendo {NUEVO_VALOR}, confirmando con Tab y guardando")
        campo.click()
        campo.fill(NUEVO_VALOR)
        # El campo solo registra lo escrito al salir de él: sin esto la
        # aplicación seguía viendo 0 y rechazaba guardar ("el valor no puede
        # ser 0"). Por eso se confirma con Tab.
        campo.press("Tab")

        # Entre un paso y otro la aplicación necesita unos instantes para
        # registrar el valor: con pausas más cortas a veces se guardaba 0.
        page.wait_for_timeout(1500)
        page.locator("#ext-gen53").click()
        page.wait_for_timeout(3000)
        page.locator("#ext-gen56").click()

        # Se da tiempo a que termine de guardar. La aplicación puede volver
        # sola a la lista o quedarse en la pantalla de edición; en ese caso se
        # va a la lista por su dirección.
        _paso("esperando a que la aplicación termine de guardar y vuelva a la lista")
        volvio = _esperar_vuelta_a_la_lista(page)
        print(f"COTIZACION: tras guardar, volvió a la lista = {volvio}; url={page.url!r}; "
              f"mensajes={_aviso_en_pantalla(page)!r}")
        if page.url != url_lista:
            # Si la aplicación se quedó en la pantalla de edición, se va a la
            # lista por su dirección.
            page.goto(url_lista)
        page.wait_for_load_state("load")

        # La cotización puede conservar su número o quedar con uno nuevo.
        numero_actual = _esperar_cotizacion_nueva(page, base)
        print(f"COTIZACION: cotización después de modificar = {numero_actual}")

        # Se vuelve a abrir y se lee lo que quedó guardado en el campo.
        _paso(f"volviendo a abrir la cotización {numero_actual} SOLO para comprobar que quedó el valor (no cambia nada)")
        page.locator(f"#edt_{numero_actual}").click()
        campo = page.locator("#ext-comp-1014")
        expect(campo).to_be_visible(timeout=20000)
        expect(campo).not_to_have_value("", timeout=10000)
        guardado = campo.input_value()
        print(f"COTIZACION: valor del campo al reabrir = {guardado!r}")
        _resaltar(page, campo, f"el mismo campo, al reabrir la cotización, vale {guardado!r}: ese es el valor guardado")
        assert _entero_de(guardado) == int(NUEVO_VALOR), (
            f"El valor no quedó guardado: se escribió {NUEVO_VALOR} y al "
            f"reabrir la cotización el campo muestra {guardado!r}"
        )


def test_eliminar_cotizacion(pagina_con_paciente: Page):
    """
    #15 - En el listado de cotizaciones, eliminar la cotización.

    Crea su propia cotización, la elimina con "Si" y verifica que desaparezca
    de la lista.
    """
    page = pagina_con_paciente

    with _mapa_si_falla(page):
        numero, base = _crear_cotizacion(page)
        _eliminar_cotizacion(page, numero)
        restantes = _ids_cotizaciones(page) - base
        assert not restantes, f"Quedaron cotizaciones sin borrar: {sorted(restantes)}"
        _paso(f"la cotización ya no está en la lista: se deja la pantalla {PAUSA_FINAL_MS // 1000} s para verla")
        page.wait_for_timeout(PAUSA_FINAL_MS)
