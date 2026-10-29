# Guion de demostración (aprox. 5 minutos)

Contexto: catálogo **ficticio** de un centro de capacitación. No hay convenios con aliados del evento. Una solicitud de inscripción no es una matrícula pagada.

1. **Tablero (30 s).** Entra como operador demo. Muestra métricas: conversaciones activas, pendientes humanas, leads calientes, solicitudes de inscripción, mediana de primera respuesta.
2. **Consulta con falta (40 s).** Simula: «quiero el curso de phyton». El asistente reconoce Python para datos y cita precio, horario y modalidad del catálogo.
3. **Dato ausente (30 s).** «¿Hay convenio y certificado internacional?» Debe decir que no está en el catálogo.
4. **Objeción de precio (40 s).** «Está muy caro, ¿me hacen descuento?» Explica valor, no inventa descuentos, no usa el precio de otro curso.
5. **Inscripción (40 s).** «Quiero inscribirme en python para datos, acepto que registren mi solicitud.» Aparece lead caliente y una solicitud, no una venta.
6. **Handover (50 s).** «Esto no sirve, quiero un asesor.» Pasa a pendiente, un solo aviso de sistema, la IA se pausa. **Tomar control** y responde como humano. El mensaje figura como asesor.
7. **Concurrencia (30 s).** Con `operador-b@demo.local` intenta tomar el mismo chat: conflicto.
8. **Reanudar (20 s).** El dueño pulsa **Reanudar IA**.

Si Docker no está disponible, esta ruta usa SQLite y adaptadores simulados. Dilo al jurado: no es el bot desplegado.
