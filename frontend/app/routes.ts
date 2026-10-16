import { type RouteConfig, index, layout, route } from "@react-router/dev/routes";

export default [
  route("health", "routes/health.ts"),
  route("login", "routes/login.tsx"),
  layout("routes/protected.tsx", [
    index("routes/home.tsx"),
    route("applications", "routes/applications.tsx"),
    route("applications/new", "routes/new-application.tsx"),
    route("applications/:id", "routes/application-detail.tsx"),
    route("applications/:id/edit", "routes/edit-application.tsx"),
  ]),
  route(".well-known/appspecific/com.chrome.devtools.json", "routes/devtools-json.ts"),
] satisfies RouteConfig;
