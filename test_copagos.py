"""
Pruebas de regresión: Copagos - Dent-OS
Casos cubiertos:
  #4  Cancelar copago generando RC (Recibo de Caja)
  #5  Cancelar copago generando FRA (Factura)
"""

import re
import pytest
from playwright.sync_api import Page, expect

from conftest import buscar_y_abrir_paciente

# Paciente que tiene un plan de tratamiento asociado a un convenio
# (contrato), de modo que al agregar un procedimiento la app abre la
# ventana de "datos adicionales" con el copago.
NOMBRE_PACIENTE_CONVENIO = "ALEXANDRA MARIA"

# Botón de ese plan en la lista de planes del paciente. El número es el
# id del plan (dato fijo, no un id autogenerado de ExtJS).
BOTON_PLAN_CONVENIO = "#deltrat_2746"

# Procedimiento del convenio que se agrega (se busca por este texto).
PROCEDIMIENTO_CONVENIO = "IMPLANTE"

# En la ventana "Realizar Pago" del copago, el campo "Concepto" decide qué
# documento se genera. En este ambiente solo existe "Factura de contado".
# Es una expresión regular que se busca entre los conceptos disponibles.
CONCEPTO_FACTURA = r"^Factura de contado$"

# Cómo empieza el número del pago en el "Listado de Pagos": FE-123 es una
# factura electrónica.
NUMERO_FACTURA = re.compile(r"^FE-\d+")


def _numero(texto: str) -> int:
    """Convierte '$ 10,000.00' o '10000.00' en el entero 10000."""
    limpio = re.sub(r"[^\d.]", "", texto.split("$")[-1])
    assert limpio, f"No se encontró un número en: {texto!r}"
    return int(float(limpio))


def _textos_pagos(page: Page) -> list:
    """Texto de cada fila del "Listado de Pagos" del plan."""
    filas = page.locator("#grid_pagos .x-grid3-row").all_inner_texts()
    return [" ".join(t.split()) for t in filas]


def _pagar_copago_de_procedimiento_de_convenio(page: Page, concepto: str) -> dict:
    """
    Agrega un procedimiento del convenio al plan, paga su copago desde la
    ventana "Realizar Pago" usando el CONCEPTO indicado (expresión regular
    que se busca entre los conceptos disponibles) y devuelve datos de lo
    ocurrido para verificar.
    """
    page.locator("#pt").click()
    page.locator(BOTON_PLAN_CONVENIO).click()

    # --- Agregar el procedimiento del convenio ---
    campo_procedimiento = page.locator("#cb_proc")
    campo_procedimiento.click()
    campo_procedimiento.fill("implante")
    # Se fuerza el evento 'keyup' que espera el filtro en vivo de ExtJS.
    campo_procedimiento.press("Backspace")
    campo_procedimiento.type("e", delay=100)
    page.wait_for_timeout(1000)

    opcion = (
        page.locator(".x-combo-list-item")
        .filter(has_text=re.compile(PROCEDIMIENTO_CONVENIO, re.IGNORECASE))
        .first
    )
    expect(opcion).to_be_visible(timeout=10000)
    opcion.click()

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


def _verificar_copago_pagado(resultado: dict, numero_esperado: "re.Pattern[str]"):
    """Comprueba el comprobante, el pago nuevo y el tipo de documento."""
    assert resultado["url_comprobante"] and resultado["url_comprobante"] != "about:blank", (
        f"El comprobante no cargó una URL válida: {resultado['url_comprobante']!r}"
    )
    pago = resultado["pago_nuevo"]
    assert pago, "No se encontró el pago nuevo en el listado de pagos"
    assert numero_esperado.search(pago), (
        f"El pago nuevo no empieza con {numero_esperado.pattern!r}: {pago!r}"
    )
    assert f"{resultado['copago']:,}" in pago, (
        f"El pago nuevo no muestra el copago {resultado['copago']:,}: {pago!r}"
    )
    assert "Pago de Copago" in pago, (
        f"El pago nuevo no tiene el detalle 'Pago de Copago': {pago!r}"
    )


def test_cancelar_copago_generando_rc(pagina_logueada: Page):
    """
    #4 - Se adjunta procedimiento asociado a un convenio y se cancela
    el copago generando Recibo de Caja.
    """
    pytest.skip(
        "Pendiente: en este ambiente el copago solo ofrece el concepto "
        "'Factura de contado' (genera FE-...). Falta saber cómo se genera "
        "el Recibo de Caja."
    )


def test_cancelar_copago_generando_fra(pagina_logueada: Page):
    """
    #5 - Se adjunta procedimiento asociado a un convenio y se cancela
    el copago generando Factura.

    Elige el concepto "Factura de contado" y verifica que el pago nuevo
    quede numerado como factura electrónica (FE-...).
    """
    page = pagina_logueada
    buscar_y_abrir_paciente(page, NOMBRE_PACIENTE_CONVENIO)

    resultado = _pagar_copago_de_procedimiento_de_convenio(page, CONCEPTO_FACTURA)

    _verificar_copago_pagado(resultado, NUMERO_FACTURA)
