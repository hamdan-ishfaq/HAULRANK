import { Alert, Box, Button, Paper, Stack, TextField, Typography } from "@mui/material";
import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE, ApiError, login } from "../api/client";

function formatLoginError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0) return err.body;
    if (err.status === 401) return "Wrong username or password (401).";
    if (err.status === 429) return "Too many login attempts (429). Wait a minute and retry.";
    if (err.status === 403) return `Forbidden (403). ${err.body}`;
    if (err.status >= 500) {
      return `Server error (${err.status}). request_id=${err.requestId || "n/a"} body=${err.body}`;
    }
    return `Login failed (${err.status}): ${err.body}`;
  }
  if (err instanceof Error) return err.message;
  return "Login failed";
}

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
    } catch (err) {
      console.error("[HaulRank] login failed", { API_BASE, err });
      setError(formatLoginError(err));
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
      <Paper sx={{ p: 4, width: 400 }} elevation={0} variant="outlined">
        <Typography variant="h4" gutterBottom>
          HaulRank
        </Typography>
        <Typography color="text.secondary" mb={1}>
          Dispatch ranking for small carriers
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" mb={2}>
          API: {API_BASE}
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
          {error && (
            <Alert severity="error" sx={{ wordBreak: "break-word" }}>
              {error}
            </Alert>
          )}
          <Button type="submit" variant="contained">
            Sign in
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}
