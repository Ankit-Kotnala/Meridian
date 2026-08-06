# @rezumi/eslint-config

Shared ESLint configuration and a small dependency-boundary check for the
Rezumi web application. Feature modules cannot depend on routes, shared code
cannot depend on product modules, and modules communicate through public entry
points rather than another module's internals.
