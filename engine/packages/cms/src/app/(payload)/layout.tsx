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

// This is the sole root layout in this app (no `src/app/layout.tsx`) — a
// Next.js "multiple root layouts" setup where the route group defines its
// own <html>/<body>. There is only one group here because this package is
// CMS-only; it has no public-facing route group.
const Layout = ({ children }: Args) => (
  <RootLayout config={config} importMap={importMap} serverFunction={serverFunction}>
    {children}
  </RootLayout>
)

export default Layout
