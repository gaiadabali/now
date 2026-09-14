import type { Metadata } from 'next'

import config from '@payload-config'
import { generatePageMetadata, RootPage } from '@payloadcms/next/views'

import { importMap } from '../importMap.js'

// Matches @payloadcms/next's own Args shape (see
// node_modules/@payloadcms/next/dist/views/Root/metadata.d.ts) exactly,
// rather than Next's generated PageProps for an optional catch-all route —
// Payload's RootPage/generatePageMetadata expect a plain string-keyed
// record with no `undefined` in the value union.
type Args = {
  params: Promise<{ segments: string[] }>
  searchParams: Promise<{ [key: string]: string | string[] }>
}

export const generateMetadata = ({ params, searchParams }: Args): Promise<Metadata> =>
  generatePageMetadata({ config, params, searchParams })

const Page = ({ params, searchParams }: Args) => RootPage({ config, importMap, params, searchParams })

export default Page
