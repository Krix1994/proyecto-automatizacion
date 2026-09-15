"""
Pruebas de regresión: Formatos de impresión - Dent-OS
Casos cubiertos:
  #9   Formatos de impresión - Factura crédito
  #10  Formatos de impresión - Factura contado
"""

import pytest
from playwright.sync_api import Page, expect


def test_imprimir_formatos_factura_credito(pagina_con_paciente: Page):
    """
    #9 - Se imprimen las facturas en todos los formatos (factura a crédito).
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")


def test_imprimir_formatos_factura_contado(pagina_con_paciente: Page):
    """
    #10 - Se imprimen las facturas en todos los formatos (factura de contado).
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")
