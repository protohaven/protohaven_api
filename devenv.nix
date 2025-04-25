{ pkgs, ... }:

{
  # https://devenv.sh/reference/options/
  packages = [
    pkgs.cypress
    # config.packages.default
  ];

  dotenv = {
    enable = true;
    filename = ".env.default";
  };

  env = {
    CYPRESS_INSTALL_BINARY = 0;
    CYPRESS_RUN_BINARY = "${pkgs.cypress}/bin/Cypress";
  };

  languages = {
    typescript.enable = true;

    javascript = {
      enable = true;
      directory = "./svelte";
      # corepack.enable = true;
      pnpm = {
        enable = true;
        install.enable = true;
      };
    };

    python = {
      enable = true;
      venv = {
        enable = true;
        requirements = ./requirements.txt;
      };
    };
  };

  scripts = {
    dev-run-docker.exec = /* sh */ ''
      docker compose watch
    '';
  };

  tasks = {
    "lint:python" = {
      before = [ "devenv:enterTest" ];

      exec = /* sh */ ''
        pylint -rn -sn \
          --generated-members=client.tasks,client.projects $(git ls-files '*.py') \
          --disable=logging-fstring-interpolation,import-error
      '';
    };
  };

  processes = {
    flask.exec = /* sh */ ''
      flask --app protohaven_api.main run
    '';

    svelte.exec = /* sh */ ''
      pushd svelte
      pnpm run dev
    '';

    nocodb.exec = /* sh */ ''
      docker compose up nocodb
    '';
  };

  # services = {
  #   postgres.enable = true;
  # };

  # enterShell = ''
  #   hello
  # '';

  enterTest = /* sh */ ''
    python -m pytest -v

    pushd svelte
    pnpm cypress run --component
    popd
  '';
}
