"""
Pruebas de regresión: Copagos - Dent-OS
Casos cubiertos:
  #4  Cancelar copago generando RC (Recibo de Caja)
  #5  Cancelar copago generando FRA (Factura)
"""

import re
from contextlib import contextmanager

from playwright.sync_api import Page, expect

# Cada caso usa un paciente que tiene un plan de tratamiento asociado a un
# convenio (contrato), de modo que al agregar un procedimiento la app abre la
# ventana de "datos adicionales" con el copago. Se indica nombre y apellido
# porque varios pacientes comparten el nombre (por ejemplo hay otra "ALEXANDRA
# MARIA", la de apellidos CLAVIJO GUERRA). El botón del plan lleva el id del
# plan (dato fijo, no un id autogenerado de ExtJS).

# Copago con FACTURA: ALEXANDRA MARIA RINCON PINEDA, plan 2746.
NOMBRE_PACIENTE_FACTURA = "ALEXANDRA MARIA"
APELLIDOS_PACIENTE_FACTURA = "RINCON PINEDA"
BOTON_PLAN_FACTURA = "#deltrat_2746"

# Copago con RECIBO DE CAJA: ABEL IBAÑES CARABALLO, plan 4119. Se usa solo
# "CARABALLO" para no depender de cómo está escrito el primer apellido.
NOMBRE_PACIENTE_RECIBO = "ABEL"
APELLIDOS_PACIENTE_RECIBO = "CARABALLO"
BOTON_PLAN_RECIBO = "#deltrat_4119"

# Procedimiento del convenio que se agrega. Se busca escribiendo "implante" y
# se elige de la lista el que se llama EXACTAMENTE así (tiene copago 10,000).
PROCEDIMIENTO_CONVENIO = "IMPLANTE"

# En la ventana "Realizar Pago" del copago, el campo "Concepto" decide qué
# documento se genera. En este ambiente solo existe "Factura de contado".
# Es una expresión regular que se busca entre los conceptos disponibles.
CONCEPTO_FACTURA = r"^Factura de contado$"

# Cómo se ve el pago nuevo en el "Listado de Pagos": una factura empieza con
# "FE-" (FE-390 ...) y un recibo de caja es solo el número (228 ...).
NUMERO_FACTURA = re.compile(r"^FE-\d+\s")
NUMERO_RECIBO = re.compile(r"^\d+\s")

# Dirección del comprobante que abre la app: cambia según el documento.
URL_FACTURA = re.compile(r"/imprimirpagopac/")
URL_RECIBO = re.compile(r"/reciboscaja/")

# Página de inicio (dashboard) de Dentos.
URL_INICIO = "https://release.dentos.co/default/index/bienvenido"

# Qué documento genera el pago de un copago NO se elige en la ventana de
# pago: lo decide esta opción del sistema (Administración > Opciones del
# sistema). Con el valor 0 el copago genera Recibo de Caja.
OPCION_DOCUMENTO_COPAGO = "Configurar documento copago"
VALOR_DOCUMENTO_RECIBO = "0"
# Valor que hace que el copago genere Factura. Es el que traía la opción
# antes de ponerla en 0; si no es "1", la prueba de factura (#5) fallará y
# mostrará el número real del pago.
VALOR_DOCUMENTO_FACTURA = "1"


def _abrir_paciente(page: Page, nombre: str, apellidos: str) -> None:
    """
    Abre al paciente desde "Listado de Pacientes". Se busca por el nombre y se
    elige la fila que coincide con nombre Y apellidos, porque el nombre solo
    lo comparten varios pacientes.
    """
    page.get_by_title("Pacientes").get_by_role("link").click()

    # Se escribe letra por letra: el filtro de la lista espera teclas.
    caja_busqueda = page.locator("input[type='text']").first
    caja_busqueda.click()
    caja_busqueda.press_sequentially(nombre, delay=80)
    page.wait_for_timeout(1000)

    fila = page.get_by_role(
        "row",
        name=re.compile(
            rf"\b{re.escape(nombre)}\b.*\b{re.escape(apellidos)}\b",
            re.IGNORECASE,
        ),
    )
    expect(fila).to_be_visible(timeout=10000)
    # Se hace clic en el texto de los apellidos (no en el centro de la fila,
    # donde cae el enlace del correo).
    fila.get_by_text(apellidos).click()


def _numero(texto: str) -> int:
    """Convierte '$ 10,000.00' o '10000.00' en el entero 10000."""
    limpio = re.sub(r"[^\d.]", "", texto.split("$")[-1])
    assert limpio, f"No se encontró un número en: {texto!r}"
    return int(float(limpio))


def _textos_pagos(page: Page) -> list:
    """Texto de cada fila del "Listado de Pagos" del plan."""
    filas = page.locator("#grid_pagos .x-grid3-row").all_inner_texts()
    return [" ".join(t.split()) for t in filas]


def _pagar_copago_de_procedimiento_de_convenio(
    page: Page, boton_plan: str, concepto: "str | None"
) -> dict:
    """
    Agrega un procedimiento del convenio al plan, paga su copago desde la
    ventana "Realizar Pago" y devuelve datos de lo ocurrido para verificar.
    CONCEPTO es una expresión regular que se busca entre los conceptos
    disponibles; si es None se deja el concepto que trae la ventana.
    """
    page.locator("#pt").click()
    page.locator(boton_plan).click()

    # --- Agregar el procedimiento del convenio ---
    campo_procedimiento = page.locator("#cb_proc")
    campo_procedimiento.click()
    campo_procedimiento.fill("implante")
    # Se fuerza el evento 'keyup' que espera el filtro en vivo de ExtJS.
    campo_procedimiento.press("Backspace")
    campo_procedimiento.type("e", delay=100)
    page.wait_for_timeout(1000)

    # Al escribir "implante" la lista trae varios procedimientos (por ejemplo
    # "CIRUGIA IMPLANTE ..."). Antes se tomaba el primero, que ya no era
    # "IMPLANTE" y tenía copago 0. Ahora se elige el que se llama EXACTAMENTE
    # como PROCEDIMIENTO_CONVENIO.
    opciones = page.locator(".x-combo-list-item:visible")
    expect(opciones.first).to_be_visible(timeout=10000)
    textos_opciones = [" ".join(t.split()) for t in opciones.all_inner_texts()]
    print(f"\nCOPAGO: opciones al buscar el procedimiento = {textos_opciones}")
    exacta = opciones.filter(
        has_text=re.compile(rf"^\s*{re.escape(PROCEDIMIENTO_CONVENIO)}\s*$")
    )
    assert exacta.count() > 0, (
        f"No hay un procedimiento llamado exactamente "
        f"{PROCEDIMIENTO_CONVENIO!r}. Opciones: {textos_opciones}"
    )
    exacta.first.click()

    campo_dientes = page.locator('input[name="tf_dientes"]')
    campo_dientes.click()
    campo_dientes.fill("12")

    page.locator("button.btn_add").click()

    # --- Ventana de "datos adicionales" (se abre sola con convenios) ---
    # No se usa el botón "Cancelar" opcional de otras pruebas: esta
    # ventana también tiene uno y lo cerraría.
    boton_pagar_datos = page.locator("#pagarFormProc button")
    expect(boton_pagar_datos).to_be_visible(timeout=20000)
    campo_copago = page.locator("#nf_cuota_moderada1")
    expect(campo_copago).not_to_have_value("", timeout=10000)
    copago = _numero(campo_copago.input_value())
    assert copago > 0, f"El copago del procedimiento es {copago}; debe ser > 0"
    boton_pagar_datos.click()

    # --- Ventana "Realizar Pago" del copago ---
    ventana_copago = page.locator(".x-window").filter(
        has=page.locator('input[name="nf_valorapagar"]')
    )
    expect(ventana_copago).to_be_visible(timeout=10000)
    campo_concepto = ventana_copago.locator('input[name="cb_conceptos"]')
    # El concepto por defecto se carga solo, un instante después de abrirse.
    expect(campo_concepto).not_to_have_value("", timeout=10000)

    valor_en_ventana = _numero(ventana_copago.locator("#valorapagarpago").inner_text())
    assert valor_en_ventana == copago, (
        f"La ventana de pago muestra {valor_en_ventana} y el copago era {copago}"
    )

    # --- Elegir el concepto (decide si se genera factura o recibo) ---
    # Los nombres vienen con un salto de línea al final: se limpian.
    conceptos = [
        c.strip()
        for c in page.evaluate(
            "() => Ext.getCmp('cb_conceptos').getStore().getRange()"
            ".map(r => r.get('nombre'))"
        )
    ]
    print(f"\nCOPAGO: conceptos disponibles = {conceptos}")
    if concepto is None:
        elegido = campo_concepto.input_value().strip()
    else:
        elegido = next(
            (c for c in conceptos if re.search(concepto, c, re.IGNORECASE)), None
        )
        assert elegido, (
            f"Ningún concepto coincide con {concepto!r}. Disponibles: {conceptos}"
        )
        if campo_concepto.input_value().strip() != elegido:
            campo_concepto.click()
            opcion_concepto = page.locator(".x-combo-list-item:visible").filter(
                has_text=re.compile(rf"^\s*{re.escape(elegido)}\s*$")
            )
            expect(opcion_concepto).to_be_visible(timeout=10000)
            opcion_concepto.click()
        expect(campo_concepto).to_have_value(
            re.compile(rf"^\s*{re.escape(elegido)}\s*$"), timeout=10000
        )

    forma_pago = ventana_copago.locator('input[name="formas_pago"]').input_value()
    pagos_antes = _textos_pagos(page)

    # Al pagar, la app abre el comprobante en una ventana nueva.
    with page.expect_popup() as popup_info:
        ventana_copago.get_by_role("button", name="Pagar", exact=True).click()
    comprobante = popup_info.value
    comprobante.wait_for_load_state()
    url_comprobante = comprobante.url
    comprobante.close()

    expect(ventana_copago).to_be_hidden(timeout=15000)

    # El pago debe aparecer como una fila nueva en el "Listado de Pagos".
    filas = page.locator("#grid_pagos .x-grid3-row")
    expect(filas).to_have_count(len(pagos_antes) + 1, timeout=15000)
    nuevos = [t for t in _textos_pagos(page) if t not in pagos_antes]

    resultado = {
        "copago": copago,
        "concepto": elegido,
        "forma_pago": forma_pago,
        "url_comprobante": url_comprobante,
        "pago_nuevo": nuevos[0] if nuevos else "",
    }
    print(f"COPAGO: valor = {copago}")
    print(f"COPAGO: concepto usado = {elegido!r}")
    print(f"COPAGO: forma de pago = {forma_pago!r}")
    print(f"COPAGO: pago nuevo en el listado = {resultado['pago_nuevo']!r}")
    print(f"COPAGO: comprobante = {url_comprobante!r}")
    return resultado


def _verificar_copago_pagado(
    resultado: dict, numero_esperado: "re.Pattern[str]", url_esperada: "re.Pattern[str]"
):
    """Comprueba el comprobante, el pago nuevo y el tipo de documento."""
    url = resultado["url_comprobante"]
    assert url and url != "about:blank", (
        f"El comprobante no cargó una URL válida: {url!r}"
    )
    assert url_esperada.search(url), (
        f"El comprobante no se abrió en {url_esperada.pattern!r}: {url!r}"
    )
    pago = resultado["pago_nuevo"]
    assert pago, "No se encontró el pago nuevo en el listado de pagos"
    assert numero_esperado.search(pago), (
        f"El número del pago nuevo no coincide con {numero_esperado.pattern!r}: "
        f"{pago!r}"
    )
    assert f"{resultado['copago']:,}" in pago, (
        f"El pago nuevo no muestra el copago {resultado['copago']:,}: {pago!r}"
    )
    assert "Pago de Copago" in pago, (
        f"El pago nuevo no tiene el detalle 'Pago de Copago': {pago!r}"
    )


def _cambiar_opcion_documento_copago(page: Page, nuevo_valor: str, estado: dict) -> None:
    """
    Cambia, en Administración > Opciones del sistema, el valor de
    "Configurar documento copago" y deja la página en el inicio. El valor
    que tenía antes se guarda en estado["anterior"] apenas se lee, para
    poder restaurarlo aunque algo falle después.
    """
    page.goto(URL_INICIO)
    page.get_by_title("Administración").get_by_role("link").click()
    page.get_by_role("link", name="Opciones del sistema").click()

    # Se escribe letra por letra: el filtro de la lista espera teclas, no
    # el relleno instantáneo de fill().
    campo_nombre = page.get_by_role("textbox", name="Nombre:")
    campo_nombre.click()
    campo_nombre.press_sequentially("copago", delay=80)

    fila = page.get_by_text(OPCION_DOCUMENTO_COPAGO)
    expect(fila).to_be_visible(timeout=15000)
    fila.click()
    page.get_by_role("button", name="Modificar").click()

    campo_valor = page.get_by_role("textbox", name="Valor:")
    # El formulario carga el valor actual un instante después de abrirse;
    # hay que esperarlo para no "restaurar" después un valor vacío.
    expect(campo_valor).not_to_have_value("", timeout=10000)
    estado["anterior"] = campo_valor.input_value()
    print(f"\nCOPAGO: '{OPCION_DOCUMENTO_COPAGO}' = {estado['anterior']!r} "
          f"-> {nuevo_valor!r}")

    campo_valor.click()
    campo_valor.fill(nuevo_valor)
    page.get_by_role("button", name="Guardar", exact=True).click()
    aceptar = page.get_by_role("button", name="Aceptar", exact=True)
    expect(aceptar).to_be_visible(timeout=10000)
    aceptar.click()

    page.goto(URL_INICIO)


@contextmanager
def _documento_copago_en(page: Page, valor: str):
    """
    Pone la opción "Configurar documento copago" en `valor` mientras dura el
    bloque y SIEMPRE la restaura al terminar, aunque la prueba falle. Es una
    opción de todo el ambiente: si quedara cambiada, la prueba de factura (#5)
    empezaría a generar recibos y fallaría.
    """
    estado: dict = {}
    try:
        _cambiar_opcion_documento_copago(page, valor, estado)
        yield
    finally:
        anterior = estado.get("anterior")
        if anterior is not None and anterior != valor:
            try:
                _cambiar_opcion_documento_copago(page, anterior, {})
                print(f"COPAGO: opción restaurada a {anterior!r}")
            except Exception:
                print(
                    f"COPAGO: ADVERTENCIA - no se pudo restaurar "
                    f"'{OPCION_DOCUMENTO_COPAGO}' a {anterior!r}. Revísala a "
                    f"mano en Administración > Opciones del sistema."
                )
                raise


def test_cancelar_copago_generando_rc(pagina_logueada: Page):
    """
    #4 - Se adjunta procedimiento asociado a un convenio y se cancela
    el copago generando Recibo de Caja.

    Con el paciente ABEL IBAÑES CARABALLO (plan 4119): pone la opción del
    sistema "Configurar documento copago" en 0, paga el copago y verifica que
    el pago nuevo sea un recibo de caja (número solo de dígitos y comprobante
    en /reciboscaja/). Al terminar vuelve a dejar la opción como estaba.
    """
    page = pagina_logueada

    with _documento_copago_en(page, VALOR_DOCUMENTO_RECIBO):
        _abrir_paciente(page, NOMBRE_PACIENTE_RECIBO, APELLIDOS_PACIENTE_RECIBO)
        resultado = _pagar_copago_de_procedimiento_de_convenio(
            page, BOTON_PLAN_RECIBO, None
        )
        _verificar_copago_pagado(resultado, NUMERO_RECIBO, URL_RECIBO)


def test_cancelar_copago_generando_fra(pagina_logueada: Page):
    """
    #5 - Se adjunta procedimiento asociado a un convenio y se cancela
    el copago generando Factura.

    Con la paciente ALEXANDRA MARIA RINCON PINEDA (plan 2746): pone la opción
    del sistema "Configurar documento copago" en 1, elige el concepto
    "Factura de contado" y verifica que el pago nuevo sea una factura
    electrónica (FE-... y comprobante en /imprimirpagopac/). Al terminar
    vuelve a dejar la opción como estaba.
    """
    page = pagina_logueada

    with _documento_copago_en(page, VALOR_DOCUMENTO_FACTURA):
        _abrir_paciente(page, NOMBRE_PACIENTE_FACTURA, APELLIDOS_PACIENTE_FACTURA)
        resultado = _pagar_copago_de_procedimiento_de_convenio(
            page, BOTON_PLAN_FACTURA, CONCEPTO_FACTURA
        )
        _verificar_copago_pagado(resultado, NUMERO_FACTURA, URL_FACTURA)
