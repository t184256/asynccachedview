{
  description = "Make asynchronous requests, online and offline";

  inputs.aiosqlitemydataclass = {
    url = "github:t184256/aiosqlitemydataclass";
    inputs.nixpkgs.follows = "nixpkgs";
    inputs.flake-utils.follows = "flake-utils";
  };

  inputs.asyncio-loop-local = {
    url = "github:t184256/asyncio-loop-local";
    inputs.nixpkgs.follows = "nixpkgs";
    inputs.flake-utils.follows = "flake-utils";
  };

  inputs.awaitable-property = {
    url = "github:t184256/awaitable-property";
    inputs.nixpkgs.follows = "nixpkgs";
    inputs.flake-utils.follows = "flake-utils";
  };

  outputs = {nixpkgs, flake-utils, ...}@inputs:
    let
      deps = pyPackages: with pyPackages; [
        aiosqlite aiohttp
        aiosqlitemydataclass
        awaitable-property
      ];
      tools = pkgs: pyPackages: (with pyPackages; [
        pytest pytestCheckHook
        coverage pytest-cov
        mypy pytest-mypy
        pytest-asyncio
        aioresponses
        asyncio-loop-local
      ] ++ [pkgs.ruff]);

      asynccachedview-package = {pkgs, python3Packages}:
        python3Packages.buildPythonPackage {
          pname = "asynccachedview";
          version = "0.0.1";
          src = ./.;
          format = "pyproject";
          propagatedBuildInputs = deps python3Packages;
          nativeBuildInputs = [ python3Packages.setuptools ];
          checkInputs = tools pkgs python3Packages;
        };

      asynccachedview-overlay = final: prev: {
        pythonPackagesExtensions =
          prev.pythonPackagesExtensions ++ [(pyFinal: pyPrev: {
            asynccachedview = final.callPackage asynccachedview-package {
              python3Packages = pyFinal;
            };
          })];
      };
      fresh-mypy-overlay = final: prev: {
        pythonPackagesExtensions =
          prev.pythonPackagesExtensions ++ [(pyFinal: pyPrev: {
            mypy =
              if prev.lib.versionAtLeast pyPrev.mypy.version "1.6.1"
              then pyPrev.mypy
              else pyPrev.mypy.overridePythonAttrs (_: {
                version = "1.6.1";
                patches = [];
                src = prev.fetchFromGitHub {
                  owner = "python";
                  repo = "mypy";
                  rev = "refs/tags/v1.6.1";
                  hash = "sha256-X15wE/XH2VBclgfLJTb3JWRdvRtNShezy85tvdeHLZw=";
                };
              });
          })];
      };
      overlay = nixpkgs.lib.composeManyExtensions [
        inputs.aiosqlitemydataclass.overlays.default
        inputs.asyncio-loop-local.overlays.default
        inputs.awaitable-property.overlays.default
        asynccachedview-overlay
      ];
      overlay-all = nixpkgs.lib.composeManyExtensions [
        overlay
        fresh-mypy-overlay
      ];
    in
      flake-utils.lib.eachDefaultSystem (system:
        let
          pkgs = import nixpkgs { inherit system; overlays = [ overlay-all ]; };
          defaultPython3Packages = pkgs.python311Packages;  # force 3.11

          asynccachedview = pkgs.callPackage asynccachedview-package {
            python3Packages = defaultPython3Packages;
          };
        in
        {
          devShells.default = pkgs.mkShell {
            buildInputs = [(defaultPython3Packages.python.withPackages deps)];
            nativeBuildInputs = tools pkgs defaultPython3Packages;
            shellHook = ''
              export PYTHONASYNCIODEBUG=1
            '';
          };
          packages.asynccachedview = asynccachedview;
          packages.default = asynccachedview;
        }
      ) // {
        overlays.default = overlay;
        overlays.asynccachedview = asynccachedview-overlay;
      };
}
