import { Box, Button, Paper, Stack, Typography } from "@mui/material";
import type { Assignment } from "../api/client";

const COLS = ["offered", "accepted", "dispatched", "delivered"] as const;

export default function AssignmentBoard({
  items,
  onAdvance,
}: {
  items: Assignment[];
  onAdvance: (a: Assignment) => void;
}) {
  return (
    <Stack direction={{ xs: "column", md: "row" }} gap={2}>
      {COLS.map((status) => (
        <Paper key={status} variant="outlined" sx={{ flex: 1, p: 1.5, minHeight: 140 }}>
          <Typography variant="subtitle2" textTransform="uppercase" mb={1}>
            {status}
          </Typography>
          {items
            .filter((a) => a.status === status)
            .map((a) => (
              <Box key={a.id} mb={1} p={1} bgcolor="#fff" borderRadius={1}>
                <Typography variant="body2">
                  Assign #{a.id} · load {a.load} · truck {a.truck}
                </Typography>
                {status !== "delivered" && (
                  <Button size="small" onClick={() => onAdvance(a)}>
                    Advance
                  </Button>
                )}
              </Box>
            ))}
        </Paper>
      ))}
    </Stack>
  );
}
