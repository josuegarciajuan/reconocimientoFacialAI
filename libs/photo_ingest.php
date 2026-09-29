<?php

/** Returns true only for final classifier inputs, never writer temporaries. */
function foto_ingestable_nombre(string $nombre): bool
{
    if (str_ends_with($nombre, ".hq.tmp.jpg")) {
        return false;
    }
    return (bool)preg_match('/\.jpg(?:\.hq)?$/i', $nombre);
}
