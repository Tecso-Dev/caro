// Render one exported component of the web app to static markup — with the
// app's own TypeScript and its own react-dom, and nothing the app does not
// already depend on.
//
//   node tests/render_view.cjs <webapp/web>  < request.json
//
// request:  {"component": "components/CarDetail.tsx", "export": "ListingFile",
//            "props": [ {...}, ... ],
//            "consts": {"module": "lib/format.ts", "names": ["NOT_A_CAR_FA"]}}
// response: {"markup": ["<div…>", ...], "consts": {"NOT_A_CAR_FA": "…"}}
//
// It exists so tests/test_api_contract.py can check what a READER gets, not
// what a component happens to mention. The Python side supplies the props
// from the real API; this side only draws them. Constants are evaluated from
// the module rather than parsed out of it, so a test that needs the sentence
// a page prints never keeps a copy of it.
'use strict';
const fs = require('fs');
const path = require('path');
const Module = require('module');

const WEB = path.resolve(process.argv[2] || 'webapp/web');
const NM = path.join(WEB, 'node_modules');
const ts = require(path.join(NM, 'typescript'));

const resolve = Module._resolveFilename;
Module._resolveFilename = function (request, parent, ...rest) {
  let req = request;
  if (req.startsWith('@/')) req = path.join(WEB, req.slice(2));
  if (path.isAbsolute(req)) {
    for (const ext of ['', '.tsx', '.ts', '/index.tsx', '/index.ts']) {
      if (fs.existsSync(req + ext) && fs.statSync(req + ext).isFile()) {
        return req + ext;
      }
    }
  }
  try {
    return resolve.call(this, req, parent, ...rest);
  } catch (e) {
    return resolve.call(this, path.join(NM, req), parent, ...rest);
  }
};

for (const ext of ['.ts', '.tsx']) {
  require.extensions[ext] = (mod, file) => {
    const out = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      fileName: file,
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.ReactJSX,
        target: ts.ScriptTarget.ES2020,
        esModuleInterop: true,
      },
    });
    mod._compile(out.outputText, file);
  };
}

const React = require(path.join(NM, 'react'));
const { renderToStaticMarkup } = require(path.join(NM, 'react-dom/server'));

const req = JSON.parse(fs.readFileSync(0, 'utf8'));
const Component = require(path.join(WEB, req.component))[req.export];
if (typeof Component !== 'function') {
  throw new Error(`${req.component} exports no component named ${req.export}`);
}
const markup = (req.props || []).map(
  (p) => renderToStaticMarkup(React.createElement(Component, p)));
const consts = {};
if (req.consts) {
  const mod = require(path.join(WEB, req.consts.module));
  for (const name of req.consts.names) consts[name] = mod[name];
}
process.stdout.write(JSON.stringify({ markup, consts }));
