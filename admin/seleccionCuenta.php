<?php

/* 
 * Selección de cuenta (REFACTOR Fase 4b/4c): validación de ?local= y PDO.
 */

require_once __DIR__ . "/../libs/db.php";

if (isset($_GET["desconectar"]) and $_GET["desconectar"] == "1") {
    $_SESSION["user"] = "";
    $_SESSION["local_id"] = "";
    $_SESSION["admin"] = "";
    unset($_SESSION["user"], $_SESSION["local_id"], $_SESSION["admin"]);
    echo "<script>location.href='login.php';</script>";
    exit;
}

// solo el admin puede cambiar de local, y el id debe ser válido
if (isset($_GET["local"]) and $_GET["local"] !== "") {
    if (!empty($_SESSION["admin"]) && (int)$_GET["local"] > 0) {
        $existe = DB::selectOne("SELECT id FROM locales WHERE id = ?", [(int)$_GET["local"]]);
        if ($existe) {
            $_SESSION["local_id"] = (int)$_GET["local"];
        }
    }
    echo "<script>location.href='index.php';</script>";
    exit;
}

$locales_admin = [];
if (!empty($_SESSION["admin"])) {
    $locales_admin = DB::select("SELECT id, nombre, url_logo FROM locales ORDER BY id ASC");
}
?>
<!-- BEGIN: Account Menu -->
<div class="intro-x dropdown w-8 h-8 relative">
    <div class="dropdown-toggle w-8 h-8 rounded-full overflow-hidden shadow-lg image-fit zoom-in scale-110">
        <img alt="<?= htmlspecialchars($local["nombre"] ?? ""); ?>" src="<?= htmlspecialchars($local["url_logo"] ?? ""); ?>">
    </div>
    <div class="dropdown-box mt-10 absolute w-56 top-0 right-0 z-20">
        <div class="dropdown-box__content box bg-theme-38 dark:bg-dark-6 text-white">
            <div class="p-4 border-b border-theme-40 dark:border-dark-3">
                <div class="font-medium"><?= htmlspecialchars($local["nombre"] ?? ""); ?></div>
            </div>
            <div class="p-2">
                <?php foreach ($locales_admin as $l): ?>
                    <a href="?local=<?= $l["id"]; ?>" class="flex items-center block p-2 transition duration-300 ease-in-out hover:bg-theme-1 dark:hover:bg-dark-3 rounded-md">
                        <img src="<?= htmlspecialchars($l["url_logo"]); ?>" style="width:30px"><?= htmlspecialchars($l["nombre"]); ?>
                    </a>
                <?php endforeach; ?>
            </div>
            <div class="p-2 border-t border-theme-40 dark:border-dark-3">
                <a href="?desconectar=1" class="flex items-center block p-2 transition duration-300 ease-in-out hover:bg-theme-1 dark:hover:bg-dark-3 rounded-md">Desconectar</a>
            </div>
        </div>
    </div>
</div>
<!-- END: Account Menu -->
