import { Box, CircularProgress, IconButton, List, ListItemButton, ListItemText, TextField, Typography } from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useParts } from "../services/parts";
import { useTranslation } from "react-i18next";

const PartsPage = () => {
  const { t } = useTranslation();
  const { data, isLoading, refetch } = useParts();

  return (
    <Box sx={{ p: 2 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
        <Typography variant="h5">{t("parts.title")}</Typography>
        <IconButton aria-label={t("actions.refresh") || "Refresh"} onClick={() => refetch()} size="large">
          <RefreshIcon />
        </IconButton>
      </Box>
      <TextField fullWidth placeholder={t("parts.search_placeholder") || ""} sx={{ mb: 2 }} />
      {isLoading && <CircularProgress aria-label={t("loading") || "Loading"} />}
      <List>
        {data?.items.map((part) => (
          <ListItemButton key={part.id} sx={{ minHeight: 56 }}>
            <ListItemText
              primary={`${part.name} (${part.sku})`}
              secondary={t("parts.qty", { qty: part.qty, min: part.min_qty })}
            />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );
};

export default PartsPage;
