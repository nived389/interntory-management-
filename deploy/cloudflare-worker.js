// Transitional gateway: preserve the existing backend until Supabase cutover.
const ORIGIN = 'https://interntory-management.onrender.com';
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/' || url.pathname === '/index.html' ||
        url.pathname === '/sw.js' || url.pathname.startsWith('/static/')) {
      return env.ASSETS.fetch(request);
    }
    const allowed = url.pathname === '/healthz' ||
      ['/api/', '/photo/', '/auth/', '/download/'].some(p => url.pathname.startsWith(p));
    if (!allowed) return new Response('Not found', {status: 404});
    const upstream = new URL(url.pathname + url.search, ORIGIN);
    const headers = new Headers(request.headers);
    headers.delete('host');
    // Never trust client-supplied proxy identity headers.
    headers.delete('x-forwarded-host');
    headers.delete('x-forwarded-for');
    headers.delete('forwarded');
    try {
      const response = await fetch(new Request(upstream, {
        method: request.method, headers,
        body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
        redirect: 'manual'
      }), {cf: {cacheTtl: 0, cacheEverything: false}});
      const result = new Response(response.body, response);
      result.headers.set('Cache-Control', 'private, no-store');
      const location = result.headers.get('Location');
      if (location && new URL(location, ORIGIN).origin === ORIGIN) {
        const target = new URL(location, ORIGIN);
        result.headers.set('Location', url.origin + target.pathname + target.search + target.hash);
      }
      return result;
    } catch {
      return Response.json({error: 'Inventory server is starting. Please try again shortly.'},
        {status: 503, headers: {'Cache-Control': 'no-store', 'Retry-After': '10'}});
    }
  }
};
