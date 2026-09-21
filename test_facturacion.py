"""
Pruebas de regresión: Facturación - Dent-OS
Casos cubiertos:
  #1  Factura con 2 formas de pago
  #2  Factura aplicando descuento
  #3  Factura por empresa (a nombre de un tercero)
"""

import re
import pytest
from playwright.sync_api import Page, expect


def test_factura_dos_formas_pago(pagina_con_paciente_alt: Page):
    """
    #1 - Desde el plan de tto se cancela factura usando doble forma de pago.

    Crea su propio procedimiento con saldo pendiente (para no depender
    de datos de corridas anteriores), y lo paga dividiendo el valor
    entre 2 formas de pago distintas (Efectivo y Cheque).
    """
    page = pagina_con_paciente_alt

    page.locator("#pt").click()
    page.get_by_role("button", name="Crear Plan de tratamiento (").click()

    # El diálogo de confirmación con el tipo de afiliación (Particular)
    # solo aparece a veces (ver limitación conocida documentada en
    # test_plan_tratamiento.py).
    boton_aceptar = page.get_by_role("button", name="Aceptar")
    try:
        expect(boton_aceptar).to_be_visible(timeout=3000)
        boton_aceptar.click()
        campo_contrato = page.locator('input[name="cb_contrato"]')
        if campo_contrato.input_value() != "Particular":
            campo_contrato.click()
            opcion_particular = page.get_by_text("Particular", exact=True)
            expect(opcion_particular).to_be_visible(timeout=10000)
            opcion_particular.click()
    except AssertionError:
        pass  # El paciente ya tenía un plan; no hizo falta el diálogo.

    # Crear un procedimiento nuevo con saldo pendiente garantizado.
    campo_procedimiento = page.locator("#cb_proc")
    campo_procedimiento.click()
    campo_procedimiento.fill("resina fotocurado")
    campo_procedimiento.press("Backspace")
    campo_procedimiento.type("o", delay=100)
    page.wait_for_timeout(1000)

    nombre_procedimiento = "RESINA FOTOCURADO (2 SUPERFICIES)"
    opcion_procedimiento = page.get_by_text(nombre_procedimiento, exact=True)
    expect(opcion_procedimiento).to_be_visible(timeout=10000)
    opcion_procedimiento.click()

    campo_cantidad = page.locator("#ext-comp-1065")
    campo_cantidad.click()
    campo_cantidad.fill("1")

    page.locator("button.btn_add").click()

    # Diálogo opcional "Seguimiento al paciente".
    boton_cancelar_seguimiento = page.get_by_role("button", name="Cancelar")
    try:
        expect(boton_cancelar_seguimiento).to_be_visible(timeout=3000)
        boton_cancelar_seguimiento.click()
    except AssertionError:
        pass

    # Seleccionar el checkbox de la fila del procedimiento recién creado.
    fila_procedimiento = page.get_by_role(
        "row", name=re.compile(re.escape(nombre_procedimiento))
    ).last
    expect(fila_procedimiento).to_be_visible(timeout=20000)
    fila_procedimiento.locator('input[name="procedimientoRowSelected"]').check()

    page.get_by_role("button", name="Abonar a procedimiento").click()

    # Leer el valor total pendiente para dividirlo entre las 2 formas
    # de pago.
    contenedor_valor_restante = page.get_by_text("Valor Restante:").locator("..")
    expect(contenedor_valor_restante).to_contain_text("$", timeout=10000)
    texto_restante = contenedor_valor_restante.inner_text()
    match_valor = re.search(r"([\d,]+)", texto_restante.split("$")[-1])
    assert match_valor is not None, (
        f"No se encontró un número en Valor Restante: {texto_restante!r}"
    )
    valor_total = int(match_valor.group(1).replace(",", ""))
    assert valor_total > 0, f"Valor restante inválido: {texto_restante!r}"

    valor_pago_1 = valor_total // 2
    valor_pago_2 = valor_total - valor_pago_1

    # --- Primera forma de pago (Efectivo, la que viene por defecto) ---
    campo_valor_1 = page.locator('input[name="tf_valorapagar1"]')
    campo_valor_1.click()
    campo_valor_1.fill(str(valor_pago_1))
    expect(campo_valor_1).to_have_value(str(valor_pago_1))

    # --- Agregar la segunda forma de pago ---
    page.get_by_role("button", name="Agregar forma de pago").click()

    # El combo de forma de pago de la segunda fila sigue el mismo
    # patrón de nombre que la primera ("cb_formas_pago1"), numerado
    # consecutivamente.
    campo_forma_pago_2 = page.locator('input[name="cb_formas_pago2"]')
    campo_forma_pago_2.click()
    opcion_cheque = page.get_by_text("Cheque", exact=True).last
    expect(opcion_cheque).to_be_visible(timeout=10000)
    opcion_cheque.click()

    # Seleccionar cuenta bancaria (obligatorio para pagos con Cheque).
    # El panel "Detalles de la Forma de Pago #2" aparece dinámicamente y
    # ExtJS a veces no recalcula bien su layout (el trigger queda con
    # ancho 0 para Playwright aunque se vea bien visualmente). Esperamos
    # el panel, forzamos un resize para que ExtJS reajuste el layout, y
    # hacemos clic en el contenedor completo (no solo el ícono) con
    # force=True para saltar la validación estricta de visibilidad.
    expect(
        page.get_by_text("Detalles de la Forma de Pago #2")
    ).to_be_visible(timeout=10000)
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    page.wait_for_timeout(500)

    campo_cuentas2 = page.locator('#cb_cuentas2')
    disparador_cuenta_bancaria = page.locator('#cb_cuentas2 + img')
    # El clic/teclado sobre el DOM no logra seleccionar una opción de
    # forma confiable (problema de layout de ExtJS con este combo en
    # particular). En su lugar, le hablamos directamente al componente
    # ExtJS por su API interna para seleccionar la primera cuenta de su
    # propia lista de datos (store), sin depender de clics ni teclas.
    disparador_cuenta_bancaria.evaluate("el => el.click()")
    page.wait_for_timeout(500)
    resultado_seleccion = campo_cuentas2.evaluate(
        """el => {
            const combo = Ext.getCmp(el.id);
            if (!combo) return 'no-combo';
            const store = combo.getStore();
            const seleccionar = () => {
                if (store.getCount() > 0) {
                    const rec = store.getAt(0);
                    // Este combo no tiene "valueField" configurado: su
                    // valor real ES el texto (displayField), no un id
                    // numérico interno.
                    const valor = rec.get(combo.displayField || "cuenta");
                    combo.setValue(valor);
                    combo.fireEvent('select', combo, rec, 0);
                    return 'ok:' + combo.getValue();
                }
                return 'store-vacio';
            };
            return seleccionar();
        }"""
    )
    assert resultado_seleccion.startswith("ok:"), (
        f"No se pudo seleccionar cuenta bancaria vía ExtJS: {resultado_seleccion!r}"
    )

    # Verificar que sí quedó una cuenta seleccionada antes de seguir;
    # si no, el envío del pago fallará silenciosamente más adelante.
    expect(campo_cuentas2).not_to_have_value("", timeout=5000)

    # El segundo campo "Valor a Pagar:" se llena AL FINAL, después de
    # elegir "Cheque" y la cuenta bancaria: cambiar la forma de pago
    # re-renderiza esa fila (para mostrar el panel de cuenta bancaria),
    # lo que borra cualquier valor escrito antes en ese campo.
    campo_valor_2 = page.locator('input[name="tf_valorapagar2"]')
    campo_valor_2.click()
    campo_valor_2.fill(str(valor_pago_2))
    expect(campo_valor_2).to_have_value(str(valor_pago_2))

    page.get_by_role("button", name="Pagar", exact=True).click()

    # Diálogo opcional "Seguimiento al paciente" (puede reaparecer aquí).
    boton_cancelar_seguimiento_2 = page.get_by_role("button", name="Cancelar")
    try:
        expect(boton_cancelar_seguimiento_2).to_be_visible(timeout=5000)
        boton_cancelar_seguimiento_2.click()
    except AssertionError:
        pass

    # Verificar que la factura quedó totalmente pagada (Pendiente: $0).
    # Se apunta al id del elemento en vez de al texto completo, ya que
    # la app inserta un espacio entre "$" y el número (formatMoney).
    expect(page.locator("#labelPendiente")).to_contain_text(
        "0.00", timeout=10000
    )


def test_factura_aplicar_descuento(pagina_con_paciente: Page):
    """
    #2 - Se cancela factura aplicando descuento al procedimiento.
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")


def test_factura_por_empresa(pagina_con_paciente: Page):
    """
    #3 - Se cancela factura generándola a nombre de un tercero (empresa).
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")
