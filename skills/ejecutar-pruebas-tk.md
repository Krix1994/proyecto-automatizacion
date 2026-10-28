---
name: "ejecutar-pruebas-tk"
description: "Ejecuta de punta a punta la prueba de un tk de DTV1 (DentOS V1): crea TS/TX, prueba en DentOS en el navegador integrado y actualiza TX y tk en Jira según el resultado."
---

# Ejecutar pruebas de un tk (DTV1 – DentOS V1)

## Disparador
Krixtina pide "ejecuta la prueba del tk X", "prueba el 6143" o "ejecuta las pruebas de mis tk listos para pruebas". Jira: synapt.atlassian.net, proyecto DTV1. Ambiente: Testing (https://testing.dentos.co). Ella quiere ver la ejecución en vivo en el **navegador integrado** (Claude Browser) y que se le cuente en el chat cada paso.

Datos fijos:
- Krixtina Yomayuza: accountId `63b310b348b367d78a17595d`.
- Campo Sprint: `customfield_10020`.
- Campo Tester: `customfield_10036`. Solo se usa para **buscar** los tk de Krixtina; nunca se llena en TS ni TX.

## Paso 0 – Verificación
1. Abrir https://testing.dentos.co/auth/login en el navegador integrado (pedir acceso al sitio con request_access si hace falta) y tomar una captura.
2. Si no hay sesión iniciada, pedirle a Krixtina que inicie sesión ella misma en el panel del navegador (o que dé un usuario de prueba de Testing). Nunca pedir ni escribir contraseñas reales.

## Paso 1 – Buscar el tk
- Si nombró un tk, usar esa clave (DTV1-XXXX).
- Si no, buscar los tk donde Krixtina es la **Tester** (campo "Tester", `customfield_10036`; NO la persona asignada), con la JQL: `project = DTV1 AND cf[10036] = 63b310b348b367d78a17595d AND status = "Listos para pruebas"`. Si hay varios, mostrar la lista y preguntar por cuál empezar. Si no devuelve nada, decírselo y preguntar qué tk probar (no tomar tk de otros por iniciativa propia).
- Leer el tk con getJiraIssue incluyendo `comment` e `issuelinks`. Base de los pasos: el comentario "Qué probar" **más reciente** del dev (anotar quién es el dev y su accountId: se le menciona tanto si hay hallazgos como si todo pasa). Revisar hallazgos previos de Krixtina y si ya hay TS/TX enlazados.
- Detectar el sprint activo: JQL `project = DTV1 AND sprint in openSprints()` pidiendo `customfield_10020`; tomar el objeto con `state = "active"` (su `id` y `name`). Si no hay sprint abierto, decírselo a Krixtina y crear el TX sin sprint.

## Paso 2 – Crear TS y TX
Usar la habilidad **jira-test-cases-tk** para redactar: mostrar en el chat los borradores del TS y del TX y **esperar el OK explícito** antes de crearlos. Enlazar ambos al tk con type "Relates".
- El **TX** se crea:
  - **asignado a Krixtina** (`assignee_account_id`: `63b310b348b367d78a17595d`),
  - **en el sprint activo** (`additional_fields`: `{"customfield_10020": <id del sprint activo>}`),
  - en estado EN EJECUCIÓN, con todos los pasos en "🕐 PENDIENTE".
- Ni el TS ni el TX llevan Tester.
- Verificar con getJiraIssue (`assignee`, `customfield_10020`) que el TX quedó asignado y en el sprint; si no, corregirlo con editJiraIssue.

## Paso 3 – Ejecutar en DentOS
- Antes de cada paso, avisar en el chat (SendUserMessage) qué se va a hacer; al terminarlo, informar el resultado con valores concretos (montos, cuentas, mensajes).
- Tomar capturas como evidencia (screenshot/zoom) en cada punto clave.
- Consejos de la app (ExtJS 3.1):
  - El panel es angosto: usar resize_window ~960x900 para ver ventanas completas y **volver a preset "desktop" al terminar**.
  - Las ventanas modales pueden quedar cortadas: moverlas con JS `Ext.WindowMgr.each(w=>{ if(w.isVisible()) w.setPosition(5,60); })`.
  - Los combos remotos de autocompletar (proveedor, producto, tercero) a veces no disparan al escribir: tras escribir, ejecutar `Ext.getCmp('<id>').doQuery('<texto>', true)` y luego hacer clic en la opción.
  - Para leer datos exactos: stores de las grillas (`Ext.getCmp('grid_...').getStore()`) o los endpoints que usa la UI (p. ej. `/comprobantes/listado/loadmovimientos` con `comprobante_id`). Los errores del servidor se ven con read_network_requests.
  - Rutas útiles: Cuentas por pagar `/cuentasxpagar/detalles`; menú contable `/default/index/contabilidad`; listado de comprobantes `/comprobantes/listado/listado`; certificado de retención `/reportes/index/certificadoretencion/`.
- Usar datos de prueba identificables (p. ej. factura "QA<tk>-1", detalle "Prueba QA DTV1-XXXX ...") y anotar los IDs creados (registros, comprobantes).
- Ejecutar **todos** los pasos aunque alguno falle, para dejar el TX completo.
- Antes de declarar un hallazgo dudoso, compararlo con el comportamiento de referencia (p. ej. el flujo equivalente que no se tocó). Si también ocurre ahí, es una observación menor, no un hallazgo del tk: se le cuenta a Krixtina en el chat, pero no va en el comentario del tk.

## Paso 4 – Si todas las pruebas pasan
1. Editar la descripción del TX: cada "🕐 PENDIENTE" → "✅ APROBADO"; Fecha de ejecución (dd-mm-aaaa), "Ejecutado por: Krixtina Yomayuza", "Resultado: Aprobado"; agregar los datos de prueba usados. (El detalle de cada paso va en el TX, no en el tk.)
2. Pasar el TX de EN EJECUCIÓN a Finalizado con la transición "EJECUCIÓN FINALIZADA" (buscar el id con getTransitionsForJiraIssue).
3. Comentar en el tk (formato ADF, con un nodo `mention` real al dev que dejó el "Qué probar", usando su accountId), **corto**, por ejemplo:
   - `@Dev se ejecutaron en Testing las pruebas del 'Qué probar' del <fecha> (TS DTV1-X / TX DTV1-Y).`
   - `✅ Pasos 1-10 aprobados (detalle en el TX DTV1-Y).`
   - `Por favor hacer el merge en release.`
   - `Datos de prueba: <IDs de registros / comprobantes>.`
4. Pasar el tk a **"Revisión de Producto"** (transición "Revisión de Producto").

## Paso 5 – Si hay hallazgos
1. Editar el TX: pasos fallidos → "❌ FALLIDO", pasos que pasaron → "✅ APROBADO"; Fecha, Ejecutado por: Krixtina Yomayuza, "Resultado: Fallido (pasos X y Y con hallazgo)". **No** cambiar el estado del TX (queda EN EJECUCIÓN).
2. Comentar en el tk (formato ADF, con un nodo `mention` real al dev que dejó el "Qué probar", usando su accountId). Estructura, igual a la del DTV1-6143:
   - Línea inicial: mención + "se ejecutaron en Testing las pruebas del 'Qué probar' del <fecha> (TS DTV1-X / TX DTV1-Y, ...). Se encontraron N hallazgos:"
   - Por cada hallazgo: 🔴 título (con el número de paso), Pasos, Resultado esperado, Resultado obtenido (mensaje de error exacto en `code`, endpoint si aplica).
   - Los pasos aprobados en **una sola línea**: `✅ Pasos 1-6, 8 y 10 aprobados (detalle en el TX DTV1-XXXX).` — sin lista detallada.
   - Una línea de `Datos de prueba:` con los IDs creados.
   - Sin sección de observaciones menores ni de evidencia. No pedir merge.
3. Pasar el tk (el tk padre, no el TS ni el TX) a **"Pendientes"** (transición "Pendientes"; buscar el id con getTransitionsForJiraIssue).

## Evidencias
Las capturas no se pueden adjuntar a Jira por el conector. Copiarlas a `/mnt/user-data/outputs/evidencias-DTV1-XXXX/` con nombres por paso (p. ej. `07-paso7-ERROR-<descripcion>.jpg`), enviarlas con SendUserFile y decirle a Krixtina cuáles pegar y dónde en el comentario (las de los errores, debajo de cada hallazgo). Si hay que editar un comentario que ella ya completó, leerlo primero en ADF y conservar los nodos `mediaSingle`/`media` (sus capturas).

## Cierre
- Volver el navegador a preset "desktop".
- Verificar con getJiraIssue que el TX quedó asignado a Krixtina, en el sprint activo y con todos los resultados; que el comentario se publicó con la mención al dev; que los enlaces "Relates" están en el tk; y que el tk quedó en el estado correcto ("Revisión de Producto" o "Pendientes").
- Resumir en el chat: resultado, hallazgos, qué se actualizó en Jira, datos de prueba que quedaron en Testing, observaciones menores si las hubo, y qué capturas pegar.