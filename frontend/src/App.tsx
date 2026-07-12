import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import DispatchPage from "./pages/DispatchPage";
import LoginPage from "./pages/LoginPage";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#1b4d3e" },
    secondary: { main: "#c45c26" },
    background: { default: "#f3f0e8" },
  },
  typography: {
    fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
    h4: { fontFamily: '"IBM Plex Serif", Georgia, serif', fontWeight: 700 },
  },
});

function Private({ children }: { children: React.ReactNode }) {
  if (!localStorage.getItem("access")) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <Private>
                <DispatchPage />
              </Private>
            }
          />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
