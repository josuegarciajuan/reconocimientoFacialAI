<?php

/*
 * Revisión — JavaScript mínimo: confirmaciones antes de mutar la galería.
 * Se ejecuta en el submit de cada botón (Aprobar / Asignar / Descartar).
 */

?>

<script>
    function rfRevisionConfirmar(accion, btn) {
        var form = (btn && btn.form) ? btn.form : null;

        if (accion === 'descartar') {
            return confirm('¿Descartar esta cara? Se borrará el pendiente sin tocar la galería.');
        }

        if (accion === 'asignar') {
            var sel = form ? form.querySelector('select[name="cod_destino"]') : document.querySelector('select[name="cod_destino"]');
            if (!sel || sel.value === '') {
                alert('Selecciona una persona existente antes de asignar.');
                return false;
            }
            return confirm('¿Asignar esta cara a la persona seleccionada?');
        }

        if (accion === 'aprobar') {
            return confirm('¿Aprobar esta cara como persona nueva?');
        }

        return true;
    }
</script>
