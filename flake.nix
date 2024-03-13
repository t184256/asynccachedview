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
      pyDeps = pyPackages: with pyPackages; [
        aiosqlite aiohttp
        aiosqlitemydataclass
        awaitable-property
      ];
      pyTestDeps = pyPackages: with pyPackages; [
        pytest pytestCheckHook pytest-asyncio
        coverage pytest-cov
        aioresponses
        asyncio-loop-local
      ];
      pyTools = pyPackages: with pyPackages; [ mypy ];

      tools = pkgs: with pkgs; [
        pre-commit
        ruff
        codespell
        actionlint
        python3Packages.pre-commit-hooks
      ];

      asynccachedview-package = {pkgs, python3Packages}:
        python3Packages.buildPythonPackage {
          pname = "asynccachedview";
          version = "0.0.1";
          src = ./.;
          disabled = python3Packages.pythonOlder "3.11";
          format = "pyproject";
          build-system = [ python3Packages.setuptools ];
          propagatedBuildInputs = pyDeps python3Packages;
          checkInputs = pyTestDeps python3Packages;
        };

      asynccachedview-overlay = final: prev: {
        pythonPackagesExtensions =
          prev.pythonPackagesExtensions ++ [(pyFinal: pyPrev: {
            asynccachedview = final.callPackage asynccachedview-package {
              python3Packages = pyFinal;
            };
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
            buildInputs = [(defaultPython3Packages.python.withPackages (
              pyPkgs: pyDeps pyPkgs ++ pyTestDeps pyPkgs ++ pyTools pyPkgs
            ))];
            nativeBuildInputs = [(pkgs.buildEnv {
              name = "asynccachedview-tools-env";
              pathsToLink = [ "/bin" ];
              paths = tools pkgs;
            })];
            shellHook = ''
              [ -e .git/hooks/pre-commit ] || \
                echo "suggestion: pre-commit install --install-hooks" >&2
              export PYTHONASYNCIODEBUG=1 PYTHONWARNINGS=error
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
