import { createBrowserRouter } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import PartsPage from "./pages/PartsPage";
import TasksPage from "./pages/TasksPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "parts", element: <PartsPage /> },
      { path: "tasks", element: <TasksPage /> }
    ]
  }
]);

export default router;
