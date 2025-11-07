import { AppBar, BottomNavigation, BottomNavigationAction, Box, Toolbar, Typography } from "@mui/material";
import Inventory2Icon from "@mui/icons-material/Inventory2";
import DashboardIcon from "@mui/icons-material/Dashboard";
import ChecklistIcon from "@mui/icons-material/Checklist";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";

const NAV_HEIGHT = 56;

const AppLayout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [value, setValue] = useState(location.pathname);

  useEffect(() => {
    setValue(location.pathname);
  }, [location.pathname]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <AppBar position="static" color="primary">
        <Toolbar>
          <Typography variant="h6" component="div">
            GEMCODEX
          </Typography>
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{ flexGrow: 1, overflow: "auto", pb: `${NAV_HEIGHT}px` }}>
        <Outlet />
      </Box>
      <BottomNavigation
        value={value}
        onChange={(_, newValue) => {
          setValue(newValue);
          navigate(newValue);
        }}
        sx={{ position: "fixed", bottom: 0, left: 0, right: 0 }}
      >
        <BottomNavigationAction label="Панель" value="/" icon={<DashboardIcon fontSize="large" />} />
        <BottomNavigationAction label="Склад" value="/parts" icon={<Inventory2Icon fontSize="large" />} />
        <BottomNavigationAction label="Задачи" value="/tasks" icon={<ChecklistIcon fontSize="large" />} />
      </BottomNavigation>
    </Box>
  );
};

export default AppLayout;
