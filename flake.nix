{
  description = "Make asynchronous requests, online and offline";

  inputs.aiosqlitemydataclass-flake = {
    url = "github:t184256/aiosqlitemydataclass";
    inputs.nixpkgs.follows = "nixpkgs";
    inputs.flake-utils.follows = "flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, aiosqlitemydataclass-flake }:
    let
      deps = pyPackages: with pyPackages; [
        aiosqlite aiohttp
        aiosqlitemydataclass
      ];
      tools = pkgs: pyPackages: (with pyPackages; [
        pytest pytestCheckHook
        coverage pytest-cov
        mypy pytest-mypy
        pytest-asyncio
        aioresponses
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
      overlay = nixpkgs.lib.composeManyExtensions [
        aiosqlitemydataclass-flake.overlays.default
        asynccachedview-overlay
      ];
    in
      flake-utils.lib.eachDefaultSystem (system:
        let
          pkgs = import nixpkgs { inherit system; overlays = [ overlay ]; };
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
