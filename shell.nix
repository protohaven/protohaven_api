let
  pkgs = import <nixpkgs> {};
  lib = pkgs.lib;
  bpp = {name, owner, repo, rev, hash}: pkgs.python3Packages.buildPythonPackage rec {
    pname = name;
    version = "0.2.15";
    src = pkgs.fetchFromGitHub {
      owner = owner;
      repo = repo;
      rev = rev;
      sha256 = hash;
    };
    #     propagatedBuildInputs = [ pkgs.python3Packages.setuptools ];
  };
in let
  apimatic-core-interfaces = bpp {
    name="apimatic-core";
    owner="apimatic";
    repo="core-interfaces-python";
    rev="0.1.5";
    hash="sha256-4was9xVP3fOqEocYIsqNflz6sARP3hPxRPcUnItmHyE="; # pragma: allowlist secret
  };
  apimatic-requests-client-adapter = bpp {
    name="apimatic-requests-client-adapter";
    owner="apimatic";
    repo="requests-client-adapter";
    rev="0.1.6";
    hash="sha256-lE6dtZIQtYBQhPACXfzX34b/PkEbOwVfWuoUd/r3Ztg="; # pragma: allowlist secret
  };
  apimatic-core = bpp {
    name="apimatic-core";
    owner="apimatic";
    repo="core-lib-python";
    rev="0.2.15";
    hash="sha256-EqFyzpwh2rB9Ck74I2C23mtMwEGPC5f157WyJ+xmv8g="; # pragma: allowlist secret
  };
  squareup = bpp {
    name = "squareup";
    owner = "square";
    repo="square-python-sdk";
    rev = "38.1.0.20240919";
    hash="sha256-zE7L8dkA2mtdXq1qmwpasjL5B9i2X05E1jPOW8Isovo="; # pragma: allowlist secret
  };
  wyze-sdk = bpp {
    name = "wyze-sdk";
    owner = "smartin015"; # was "shauntarves";
    repo = "wyze-sdk";
    rev = "0277653e3286d539a1e861059a6f98ed9224ac3a";
    hash="sha256-ICfByXLJ4aNTJhajZTiX8LhVf5imkaMUqSHagUzr25g="; # pragma: allowlist secret
  };
  mintotp = bpp {
    name = "mintotp";
    owner = "susam";
    repo = "mintotp";
    rev = "0.3.0";
    hash = "sha256-J5a1FjDsi37uBZtkx5LyWHG2klRjUtDBYyangfR4Pnc="; # pragma: allowlist secret
  };
in pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages (python-pkgs: with python-pkgs; [
        # Devtools
        pip
        pytest
        pytest-cov
        pytest-xdist
        pytest-asyncio
        pylint
        black
        isort
        pytest-mock

        # Runtime requirements
        python-dateutil
        jinja2
        pyyaml
        flask
        flask-cors
        flask-sock
        google-api-python-client google-auth-httplib2 google-auth-oauthlib
        python-dotenv
        asana
        requests
        beautifulsoup4
        pulp
        holidays
        markdown
        openai

        # Square & deps
        squareup
        apimatic-core
        apimatic-core-interfaces
        apimatic-requests-client-adapter
        cachecontrol
        jsonpickle
        jsonpointer
        deprecation

        # Wyze & deps
        wyze-sdk
        setuptools
        pycryptodomex
        mintotp

        discordpy

    ]))
  ];
}
