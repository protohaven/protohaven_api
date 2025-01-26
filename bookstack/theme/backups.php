<?php
use BookStack\Theming\ThemeEvents;
use BookStack\Facades\Theme;
use Illuminate\Routing\Router;
use Illuminate\Http\Request;

function run_mysqldump($outpath) {
  $db_user = env('DB_USERNAME');
  $db_pass = env('DB_PASSWORD');
  $db_host = env('DB_HOST');
  $db_port = env('DB_PORT');
  $db_name = env('DB_DATABASE');
  $output = null;
  $retval = null;
  $cmd = "mysqldump -P $db_port -h $db_host -u $db_user '-p$db_pass' $db_name | gzip > $outpath";
  Log::info("$cmd\n");
  exec($cmd, $output, $retval);
  return $retval;
}

function run_filedump($outpath) {
  $output = null;
  $retval = null;
  # Note the -h flag - this dereferences symlinks to follow e.g.
  # /app/www/public/uploads -> /config/www/uploads
  $cmd = "tar -czvf $outpath /config/www";
  Log::info("$cmd\n");
  exec($cmd, $output, $retval);
  return $retval;
}

Theme::listen(ThemeEvents::ROUTES_REGISTER_WEB, function (Router $router) {
  $router->get('/backups/dump_db', function (Request $request) {
    Log::info("dump_db called");
    $path = "/tmp/db_dump.sql.gz";
    $retval = run_mysqldump($path);
    if ($retval != 0) {
      return response("mysqldump error $retval", 500);
    }
    ob_end_clean();
    return response()->download($path, "db_dump.sql.gz", []);
  });

  $router->get('/backups/dump_files', function (Request $request) {
    Log::info("dump_files called");
    $path = "/tmp/files_dump.tar.gz";
    $retval = run_filedump($path);
    if ($retval != 0) {
      return response("file dump error $retval", 500);
    }
    ob_end_clean();
    return response()->download($path, "files_dump.tar.gz", []);
  });
});

?>
