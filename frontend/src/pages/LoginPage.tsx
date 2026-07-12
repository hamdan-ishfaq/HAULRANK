import { Alert, Box, Button, Paper, Stack, TextField, Typography } from "@mui/material";
import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/client";

export default function LoginPage() {
  const nav = useNavigate();
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("demo-pass-123");
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await login(username, password);
      nav("/");
    } catch {
      setError("Login failed");
    }
  }

  return (
    <Box
      minHeight="100vh"
      display="flex"
      alignItems="center"
      justifyContent="center"
      sx={{
        background:
          "radial-gradient(ellipse at 20% 20%, #dce8e2 0%, transparent 50%), linear-gradient(160deg, #f3f0e8, #e5ebe7)",
      }}
    >
      <Paper sx={{ p: 4, width: 360 }} elevation={0} variant="outlined">
        <Typography variant="h4" gutterBottom>
          HaulRank
        </Typography>
        <Typography color="text.secondary" mb={2}>
          Dispatch ranking for small carriers
        </Typography>
        <Stack component="form" gap={2} onSubmit={onSubmit}>
          <TextField
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            fullWidth
          />
          <TextField
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            fullWidth
          />
          {error && <Alert severity="error">{error}</Alert>}
          <Button type="submit" variant="contained">
            Sign in
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}
