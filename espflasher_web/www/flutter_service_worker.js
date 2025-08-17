'use strict';
const MANIFEST = 'flutter-app-manifest';
const TEMP = 'flutter-temp-cache';
const CACHE_NAME = 'flutter-app-cache';

const RESOURCES = {"assets/AssetManifest.bin": "f091c746f902b7f0df0bffdc13520dbc",
"assets/AssetManifest.bin.json": "d4cee2e6acf5a3d14493e9bb4d8c573c",
"assets/AssetManifest.json": "fe504b68e5172431a0ef31af9fb473d9",
"assets/assets/displays.json": "daeffccf5d4c17ffa997d8ddb2a99a8e",
"assets/assets/esp32_pinout.png": "8bf8fca2de6137f3de06e441f0a10c62",
"assets/assets/esp8266_NodeMCU_pinout.png": "52d8a50b06d037bcd7cb56ef6f640abd",
"assets/assets/esp8266_WemosD1Mini_pinout.png": "62ed60bedf1cea81c8e51f8332186077",
"assets/assets/icons/esphome_mdi_icons.json": "30cb9bb13b4b5089a4744af57be62b5b",
"assets/assets/logo.png": "54dce9d3159632c23fcc28e42928035a",
"assets/assets/sensors.json": "f53adda44d2a8fb592a5e2b25422dff2",
"assets/assets/templates.json": "b346531b31b4926363d52c0ce7535146",
"assets/assets/wiring/dht.png": "39b9a4795ad2d4b43858fcc3641fb325",
"assets/assets/wiring/ds18b20.png": "bc02f333c7af4cd6ea44ce7efbc3bcbb",
"assets/assets/wiring/HC-SR04.png": "eb0e850b1d9a41ef66807a5d3abe7a60",
"assets/assets/wiring/ILI9341.png": "9ee0e010eeebaaaaf717159676cfbf1b",
"assets/assets/wiring/LCD_PCF8574.png": "e2a8aaeb2313a466df9e47a1a741e640",
"assets/assets/wiring/PIR.png": "da480ad9820649511838ec634a06cddf",
"assets/assets/wiring/Reed_Switch.png": "3958553f8485d423463a718973aa50f9",
"assets/assets/wiring/Rotary_Encoder.png": "2b66d73ceb626a4694645caadfcca91a",
"assets/assets/wiring/SH1106.png": "b824b19aab0fdda0efeca38aba9a332e",
"assets/assets/wiring/SSD1306.png": "356bbb08a337ffda8afb56febea74e69",
"assets/assets/wiring/ST7735.png": "48fe247ad43745bd7f3eab8e9e213779",
"assets/FontManifest.json": "2e958424c921b963ec9a67a9cd8224ad",
"assets/fonts/MaterialIcons-Regular.otf": "e7069dfd19b331be16bed984668fe080",
"assets/NOTICES": "653114087e6034f46c0fb93aa9093fee",
"assets/packages/cupertino_icons/assets/CupertinoIcons.ttf": "b93248a553f9e8bc17f1065929d5934b",
"assets/packages/flutter_material_design_icons/assets/materialdesignicons-webfont.ttf": "6e435534bd35da5fef04168860a9b8fa",
"assets/shaders/ink_sparkle.frag": "ecc85a2e95f5e9f53123dcaf8cb9b6ce",
"canvaskit/canvaskit.js": "728b2d477d9b8c14593d4f9b82b484f3",
"canvaskit/canvaskit.js.symbols": "bdcd3835edf8586b6d6edfce8749fb77",
"canvaskit/canvaskit.wasm": "7a3f4ae7d65fc1de6a6e7ddd3224bc93",
"canvaskit/chromium/canvaskit.js": "8191e843020c832c9cf8852a4b909d4c",
"canvaskit/chromium/canvaskit.js.symbols": "b61b5f4673c9698029fa0a746a9ad581",
"canvaskit/chromium/canvaskit.wasm": "f504de372e31c8031018a9ec0a9ef5f0",
"canvaskit/skwasm.js": "ea559890a088fe28b4ddf70e17e60052",
"canvaskit/skwasm.js.symbols": "e72c79950c8a8483d826a7f0560573a1",
"canvaskit/skwasm.wasm": "39dd80367a4e71582d234948adc521c0",
"favicon.png": "dee2d928427abd3e5d77e742b47850f3",
"flutter.js": "83d881c1dbb6d6bcd6b42e274605b69c",
"flutter_bootstrap.js": "d3cda5f234f9cb448811f78d66036ed8",
"icons/Icon-192.png": "0ccc60cc5923527309fa0a0dfe5e934d",
"icons/Icon-512.png": "acb72224ca1ca4f09fae3605593f7054",
"icons/Icon-maskable-192.png": "0ccc60cc5923527309fa0a0dfe5e934d",
"icons/Icon-maskable-512.png": "acb72224ca1ca4f09fae3605593f7054",
"index.html": "15ef8978d53f9d90418a24a8dfde5051",
"/": "15ef8978d53f9d90418a24a8dfde5051",
"main.dart.js": "38d4018e1dec3b68e58626d906864255",
"manifest.json": "bd1d35e93a9d4603987e0c66b61da386",
"version.json": "72f5efe15d0a120990d57ea380726496"};
// The application shell files that are downloaded before a service worker can
// start.
const CORE = ["main.dart.js",
"index.html",
"flutter_bootstrap.js",
"assets/AssetManifest.bin.json",
"assets/FontManifest.json"];

// During install, the TEMP cache is populated with the application shell files.
self.addEventListener("install", (event) => {
  self.skipWaiting();
  return event.waitUntil(
    caches.open(TEMP).then((cache) => {
      return cache.addAll(
        CORE.map((value) => new Request(value, {'cache': 'reload'})));
    })
  );
});
// During activate, the cache is populated with the temp files downloaded in
// install. If this service worker is upgrading from one with a saved
// MANIFEST, then use this to retain unchanged resource files.
self.addEventListener("activate", function(event) {
  return event.waitUntil(async function() {
    try {
      var contentCache = await caches.open(CACHE_NAME);
      var tempCache = await caches.open(TEMP);
      var manifestCache = await caches.open(MANIFEST);
      var manifest = await manifestCache.match('manifest');
      // When there is no prior manifest, clear the entire cache.
      if (!manifest) {
        await caches.delete(CACHE_NAME);
        contentCache = await caches.open(CACHE_NAME);
        for (var request of await tempCache.keys()) {
          var response = await tempCache.match(request);
          await contentCache.put(request, response);
        }
        await caches.delete(TEMP);
        // Save the manifest to make future upgrades efficient.
        await manifestCache.put('manifest', new Response(JSON.stringify(RESOURCES)));
        // Claim client to enable caching on first launch
        self.clients.claim();
        return;
      }
      var oldManifest = await manifest.json();
      var origin = self.location.origin;
      for (var request of await contentCache.keys()) {
        var key = request.url.substring(origin.length + 1);
        if (key == "") {
          key = "/";
        }
        // If a resource from the old manifest is not in the new cache, or if
        // the MD5 sum has changed, delete it. Otherwise the resource is left
        // in the cache and can be reused by the new service worker.
        if (!RESOURCES[key] || RESOURCES[key] != oldManifest[key]) {
          await contentCache.delete(request);
        }
      }
      // Populate the cache with the app shell TEMP files, potentially overwriting
      // cache files preserved above.
      for (var request of await tempCache.keys()) {
        var response = await tempCache.match(request);
        await contentCache.put(request, response);
      }
      await caches.delete(TEMP);
      // Save the manifest to make future upgrades efficient.
      await manifestCache.put('manifest', new Response(JSON.stringify(RESOURCES)));
      // Claim client to enable caching on first launch
      self.clients.claim();
      return;
    } catch (err) {
      // On an unhandled exception the state of the cache cannot be guaranteed.
      console.error('Failed to upgrade service worker: ' + err);
      await caches.delete(CACHE_NAME);
      await caches.delete(TEMP);
      await caches.delete(MANIFEST);
    }
  }());
});
// The fetch handler redirects requests for RESOURCE files to the service
// worker cache.
self.addEventListener("fetch", (event) => {
  if (event.request.method !== 'GET') {
    return;
  }
  var origin = self.location.origin;
  var key = event.request.url.substring(origin.length + 1);
  // Redirect URLs to the index.html
  if (key.indexOf('?v=') != -1) {
    key = key.split('?v=')[0];
  }
  if (event.request.url == origin || event.request.url.startsWith(origin + '/#') || key == '') {
    key = '/';
  }
  // If the URL is not the RESOURCE list then return to signal that the
  // browser should take over.
  if (!RESOURCES[key]) {
    return;
  }
  // If the URL is the index.html, perform an online-first request.
  if (key == '/') {
    return onlineFirst(event);
  }
  event.respondWith(caches.open(CACHE_NAME)
    .then((cache) =>  {
      return cache.match(event.request).then((response) => {
        // Either respond with the cached resource, or perform a fetch and
        // lazily populate the cache only if the resource was successfully fetched.
        return response || fetch(event.request).then((response) => {
          if (response && Boolean(response.ok)) {
            cache.put(event.request, response.clone());
          }
          return response;
        });
      })
    })
  );
});
self.addEventListener('message', (event) => {
  // SkipWaiting can be used to immediately activate a waiting service worker.
  // This will also require a page refresh triggered by the main worker.
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
    return;
  }
  if (event.data === 'downloadOffline') {
    downloadOffline();
    return;
  }
});
// Download offline will check the RESOURCES for all files not in the cache
// and populate them.
async function downloadOffline() {
  var resources = [];
  var contentCache = await caches.open(CACHE_NAME);
  var currentContent = {};
  for (var request of await contentCache.keys()) {
    var key = request.url.substring(origin.length + 1);
    if (key == "") {
      key = "/";
    }
    currentContent[key] = true;
  }
  for (var resourceKey of Object.keys(RESOURCES)) {
    if (!currentContent[resourceKey]) {
      resources.push(resourceKey);
    }
  }
  return contentCache.addAll(resources);
}
// Attempt to download the resource online before falling back to
// the offline cache.
function onlineFirst(event) {
  return event.respondWith(
    fetch(event.request).then((response) => {
      return caches.open(CACHE_NAME).then((cache) => {
        cache.put(event.request, response.clone());
        return response;
      });
    }).catch((error) => {
      return caches.open(CACHE_NAME).then((cache) => {
        return cache.match(event.request).then((response) => {
          if (response != null) {
            return response;
          }
          throw error;
        });
      });
    })
  );
}
