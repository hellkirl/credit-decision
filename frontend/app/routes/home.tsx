import { redirect } from "react-router";

export function clientLoader() {
  throw redirect("/applications");
}

export default function Home() {
  return null;
}
