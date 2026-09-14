import type { ServerFunctionClient } from 'payload'

import '@payloadcms/next/css'
import { handleServerFunctions, RootLayout } from '@payloadcms/next/layouts'
import React from 'react'

import config from '@payload-config'
import { importMap } from './admin/importMap.js'

type Args = {
  children: React.ReactNode
}

const serverFunction: ServerFunctionClient = async function (args) {
  'use server'
  return handleServerFunctions({
    ...args,
    config,
    importMap,
  })
}

// One of TWO root layouts in this app. `(console)` has its own, and there
// is deliberately no shared `src/app/layout.tsx` — Next only permits
// multiple root layouts when no ancestor layout exists. Payload ships its
// own <html>/<body> and its own CSS reset, which must not be wrapped in
// the console chrome.
//
// Originally copied from engine/packages/cms — a
// Next.js "multiple root layouts" setup where the route group defines its
// own <html>/<body>. There is only one group here because this package is
// the two apps host Payload the same way.
const Layout = ({ children }: Args) => (
  <RootLayout config={config} importMap={importMap} serverFunction={serverFunction}>
    {children}
  </RootLayout>
)

export default Layout
