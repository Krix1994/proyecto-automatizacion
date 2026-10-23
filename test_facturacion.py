"""
Pruebas de regresión: Facturación - Dent-OS
Casos cubiertos:
  #1  Factura con 2 formas de pago
  #2  Factura aplicando descuento
  #3  Factura por empresa (a nombre de un tercero)
"""

import re
from playwright.sync_api import Page, expect

# Texto que muestra la app cuando ya no queda saldo: "$ 0.00".
# OJO: no se puede verificar con to_contain_text("0.00"), porque
# "$ 80,000.00" o "$ 40,000.00" también contienen "0.00" y la prueba
# pasaría aunque el pago no se hubiera completado.
PENDIENTE_EN_CERO = re.compile(r"^\s*\$\s*0(\.0+)?\s*$")

# Empresa (tercero) que YA existe en el sistema y se usa en "Facturar por
# empresa". Se busca escribiendo EMPRESA_BUSQUEDA (mínimo 3 letras) en el
# campo Nit y se elige de la lista la opción EMPRESA_NOMBRE (NIT + nombre).
EMPRESA_BUSQUEDA = "YOMAU"
EMPRESA_NOMBRE = "9002348999 YOMAUTOS"


def _leer_monto(texto: str) -> int:
    """Convierte un texto como '$ 80,000.00' en el entero 80000."""
    coincidencia = re.search(r"([\d,]+)", texto.split("$")[-1])
    assert coincidencia is not None, f"No se encontró un monto en: {texto!r}"
    return int(coincidencia.group(1).replace(",", ""))


def _regex_monto(valor: int) -> "re.Pattern[str]":
    """Regex que acepta SOLO el monto exacto: '$ 72,000.00', '$72,000'..."""
    formateado = f"{valor:,}"
    return re.compile(rf"^\s*\$\s*{re.escape(formateado)}(\.0+)?\s*$")


def _crear_procedimiento_y_abrir_pago(page: Page) -> None:
    """
    Deja abierta la ventana "Realizar Pago" con un procedimiento recién
    creado (RESINA FOTOCURADO (2 SUPERFICIES)), con todo su saldo
    pendiente. Así cada prueba no depende de datos de corridas anteriores.
    """
    page.locator("#pt").click()
    page.get_by_role("button", name="Crear Plan de tratamiento (").click()

    # Tras pulsar "Crear Plan de tratamiento" puede salir primero la
    # ventana "Seleccione un doctor" (con Aceptar) o, si no sale, abrirse
    # directo el plan. Antes se esperaba el botón solo 3 s y, si la ventana
    # tardaba más, la prueba la ignoraba y se quedaba esperando un campo
    # que todavía no existía. Ahora se espera (hasta 30 s) lo PRIMERO que
    # aparezca: la ventana del doctor o el campo "Procedimiento".
    boton_aceptar = page.get_by_role("button", name="Aceptar", exact=True)
    campo_procedimiento = page.locator("#cb_proc")
    boton_aceptar.or_(campo_procedimiento).first.wait_for(
        state="visible", timeout=30000
    )
    if boton_aceptar.is_visible():
        boton_aceptar.click()
        # Si la afiliación no quedó en "Particular", se corrige.
        campo_contrato = page.locator('input[name="cb_contrato"]')
        if campo_contrato.input_value() != "Particular":
            campo_contrato.click()
            opcion_particular = page.get_by_text("Particular", exact=True)
            expect(opcion_particular).to_be_visible(timeout=10000)
            opcion_particular.click()

    # Crear un procedimiento nuevo con saldo pendiente garantizado.
    campo_procedimiento.click()
    campo_procedimiento.fill("resina fotocurado")
    campo_procedimiento.press("Backspace")
    campo_procedimiento.type("o", delay=100)
    page.wait_for_timeout(1000)

    nombre_procedimiento = "RESINA FOTOCURADO (2 SUPERFICIES)"
    opcion_procedimiento = page.get_by_text(nombre_procedimiento, exact=True)
    expect(opcion_procedimiento).to_be_visible(timeout=10000)
    opcion_procedimiento.click()

    # Se ubican por "name" (estable) y no por el id autogenerado de
    # ExtJS (#ext-comp-NNNN), que cambia si cambia la pantalla.
    page.locator('input[name="tf_cantidad"]').fill("1")
    page.locator('input[name="tf_dientes"]').fill("1")

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
    expect(page.locator("#valorapagar1")).to_be_visible(timeout=10000)


def test_factura_dos_formas_pago(pagina_con_paciente_alt: Page):
    """
    #1 - Desde el plan de tto se cancela factura usando doble forma de pago.

    Crea su propio procedimiento con saldo pendiente (para no depender
    de datos de corridas anteriores), y lo paga dividiendo el valor
    entre 2 formas de pago distintas (Efectivo y Cheque).
    """
    page = pagina_con_paciente_alt

    _crear_procedimiento_y_abrir_pago(page)

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

    # Verificar que la factura quedó totalmente pagada (Pendiente: $ 0.00).
    # Se apunta al id del elemento (la app inserta un espacio entre "$" y
    # el número) y se exige que el texto sea EXACTAMENTE cero.
    expect(page.locator("#labelPendiente")).to_have_text(
        PENDIENTE_EN_CERO, timeout=10000
    )


def test_factura_aplicar_descuento(pagina_con_paciente_alt: Page):
    """
    #2 - Se cancela factura aplicando descuento al procedimiento.

    Crea su propio procedimiento con saldo pendiente, aplica un descuento
    del 10% desde la ventana de pago, y paga con Efectivo el valor que
    queda después del descuento. Verifica que el pendiente quede en $ 0.00.
    """
    page = pagina_con_paciente_alt

    _crear_procedimiento_y_abrir_pago(page)

    # Se trabaja dentro de la ventana "Realizar Pago": en la pantalla hay
    # DOS botones "Aplicar descuento" (uno en la página y otro en la
    # ventana) y el nombre solo cambia en mayúsculas.
    ventana_pago = page.locator(".x-window").filter(
        has=page.locator('input[name="tf_valorapagar1"]')
    )
    valor_total = _leer_monto(ventana_pago.locator("#valorapagar1").inner_text())
    assert valor_total > 0, f"Valor restante inválido: {valor_total}"

    descuento = valor_total // 10
    a_pagar = valor_total - descuento
    assert descuento > 0, f"Descuento inválido para el total {valor_total}"

    # --- Aplicar el descuento ---
    ventana_pago.get_by_role("button", name="Aplicar descuento", exact=True).click()

    ventana_descuento = page.locator(".x-window").filter(
        has=page.locator('input[name="tf_valorDescuento"]')
    )
    expect(ventana_descuento).to_be_visible(timeout=10000)
    ventana_descuento.locator('input[name="tf_valorDescuento"]').fill(str(descuento))
    ventana_descuento.locator('textarea[name="tf_detalleDescuento"]').fill(
        "Descuento de prueba automatizada"
    )
    ventana_descuento.get_by_role("button", name="Aplicar", exact=True).click()
    expect(ventana_descuento).to_be_hidden(timeout=10000)

    # La ventana de pago debe reflejar el descuento y el nuevo restante.
    expect(ventana_pago.locator("#valordescuento")).to_have_text(
        _regex_monto(descuento), timeout=10000
    )
    expect(ventana_pago.locator("#valorapagar1")).to_have_text(
        _regex_monto(a_pagar), timeout=10000
    )

    # --- Pagar lo que queda después del descuento (Efectivo, por defecto) ---
    # Al aplicar el descuento la app limpia "Valor a Pagar", hay que llenarlo.
    campo_valor_1 = page.locator('input[name="tf_valorapagar1"]')
    campo_valor_1.click()
    campo_valor_1.fill(str(a_pagar))
    expect(campo_valor_1).to_have_value(str(a_pagar))

    ventana_pago.get_by_role("button", name="Pagar", exact=True).click()

    # Diálogo opcional "Seguimiento al paciente".
    boton_cancelar_seguimiento = page.get_by_role("button", name="Cancelar")
    try:
        expect(boton_cancelar_seguimiento).to_be_visible(timeout=5000)
        boton_cancelar_seguimiento.click()
    except AssertionError:
        pass

    # Con descuento + pago el procedimiento debe quedar sin saldo.
    expect(page.locator("#labelPendiente")).to_have_text(
        PENDIENTE_EN_CERO, timeout=10000
    )


def test_factura_por_empresa(pagina_con_paciente_alt: Page):
    """
    #3 - Se cancela factura generándola a nombre de un tercero (empresa).

    Crea su propio procedimiento con saldo pendiente, pulsa "Facturar por
    empresa", elige la empresa EMPRESA_NOMBRE en el campo Nit y paga todo
    el valor en Efectivo. Verifica que el pendiente quede en $ 0.00.
    """
    page = pagina_con_paciente_alt

    _crear_procedimiento_y_abrir_pago(page)

    ventana_pago = page.locator(".x-window").filter(
        has=page.locator('input[name="tf_valorapagar1"]')
    )
    valor_total = _leer_monto(ventana_pago.locator("#valorapagar1").inner_text())
    assert valor_total > 0, f"Valor restante inválido: {valor_total}"

    # --- Elegir la empresa a la que se factura ---
    ventana_pago.get_by_role("button", name="Facturar por empresa", exact=True).click()
    campo_nit = ventana_pago.locator('input[name="cb_nit_add"]')
    expect(campo_nit).to_be_visible(timeout=10000)

    # La lista de empresas se carga mientras se escribe (hay que teclear
    # letra por letra: con fill() la app no lanza la búsqueda). Y hay que
    # ELEGIR la opción de la lista: si solo se escribe, el campo se borra
    # al salir y no queda ninguna empresa seleccionada.
    campo_nit.click()
    campo_nit.press_sequentially(EMPRESA_BUSQUEDA, delay=100)
    opcion_empresa = page.locator(".x-combo-list-item").filter(
        has_text=re.compile(rf"^\s*{re.escape(EMPRESA_NOMBRE)}\s*$")
    )
    expect(opcion_empresa).to_be_visible(timeout=15000)
    opcion_empresa.click()
    expect(campo_nit).to_have_value(re.compile(re.escape(EMPRESA_NOMBRE)))

    # --- Pagar el total en Efectivo (forma de pago por defecto) ---
    ventana_pago.locator('textarea[name="tf_detalle"]').fill("PRUEBA AUTOMATIZADA")
    campo_valor_1 = page.locator('input[name="tf_valorapagar1"]')
    campo_valor_1.click()
    campo_valor_1.fill(str(valor_total))
    expect(campo_valor_1).to_have_value(str(valor_total))

    ventana_pago.get_by_role("button", name="Pagar", exact=True).click()

    # Diálogo opcional "Seguimiento al paciente".
    boton_cancelar_seguimiento = page.get_by_role("button", name="Cancelar")
    try:
        expect(boton_cancelar_seguimiento).to_be_visible(timeout=5000)
        boton_cancelar_seguimiento.click()
    except AssertionError:
        pass

    # El procedimiento debe quedar sin saldo.
    expect(page.locator("#labelPendiente")).to_have_text(
        PENDIENTE_EN_CERO, timeout=10000
    )
