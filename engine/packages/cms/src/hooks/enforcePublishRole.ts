import type { CollectionBeforeChangeHook } from 'payload'

import { canPublish } from '../access'

/**
 * Authors can write and save drafts freely, but only editor/admin may move
 * a document into the published state (ARCHITECTURE.md editorial-essentials
 * requirement: "roles (editor/author/admin)"). Payload's REST/local API
 * both route through `beforeChange`, so this holds for the admin UI, the
 * REST API and any local-API script (including our own verification
 * scripts) alike — there is no separate "trusted" path.
 *
 * Admins/editors are exempt. `req.user` is absent for unauthenticated
 * requests, which Payload's collection-level `access.update` already
 * blocks before this hook runs; this is a second, explicit belt-and-braces
 * check specifically on the publish transition.
 */
export const enforcePublishRole: CollectionBeforeChangeHook = ({ data, originalDoc, req }) => {
  const movingToPublished = data._status === 'published' && originalDoc?._status !== 'published'

  if (movingToPublished && !canPublish(req.user)) {
    throw new Error(
      'Only editor or admin roles may publish. Save as draft and ask an editor to publish it.',
    )
  }

  return data
}
