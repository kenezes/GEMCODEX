import { Box, List, ListItem, ListItemText, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";

const TasksPage = () => {
  const { t } = useTranslation();

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h5" gutterBottom>
        {t("tasks.title")}
      </Typography>
      <List>
        <ListItem sx={{ minHeight: 56 }}>
          <ListItemText primary={t("tasks.placeholder") || ""} secondary={t("tasks.placeholder_hint") || ""} />
        </ListItem>
      </List>
    </Box>
  );
};

export default TasksPage;
