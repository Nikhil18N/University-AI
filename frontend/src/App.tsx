import { useState } from "react";
import ChatPage from "./pages/ChatPage";
import AdminPage from "./pages/AdminPage";
import "./index.css";

function App() {
  const [view, setView] = useState<"chat" | "admin">("chat");

  return view === "admin" ? (
    <AdminPage onBackToChat={() => setView("chat")} />
  ) : (
    <ChatPage onOpenAdmin={() => setView("admin")} />
  );
}

export default App;
