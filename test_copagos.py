"""
Pruebas de regresión: Copagos - Dent-OS
Casos cubiertos:
  #4  Cancelar copago generando RC (Recibo de Caja)
  #5  Cancelar copago generando FRA (Factura)
"""

import pytest
from playwright.sync_api import Page, expect


def test_cancelar_copago_generando_rc(pagina_con_paciente: Page):
    """
    #4 - Se adjunta procedimiento asociado a un convenio y se cancela
    el copago generando Recibo de Caja.
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")


def test_cancelar_copago_generando_fra(pagina_con_paciente: Page):
    """
    #5 - Se adjunta procedimiento asociado a un convenio y se cancela
    el copago generando Factura.
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")
