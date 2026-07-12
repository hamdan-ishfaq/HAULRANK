import {
  AppBar,
  Box,
  Button,
  Chip,
  Collapse,
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import type { GridColDef } from "@mui/x-data-grid";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type {
  Assignment,
  RankResponse,
  RankResult,
  Truck,
} from "../api/client";
import AssignmentBoard from "../components/AssignmentBoard";

const NEXT: Record<string, string | null> = {
  offered: "accepted",
  accepted: "dispatched",
  dispatched: "delivered",
  delivered: null,
};

function FactorChips({ row }: { row: RankResult }) {
  const items = [
    { label: "rate", v: row.rate_per_mile_score, color: "success" as const },
    { label: "deadhead", v: 1 - row.deadhead_penalty, color: "warning" as const },
    { label: "fuel", v: row.fuel_efficiency_score, color: "info" as const },
    { label: "HOS", v: row.hos_feasibility, color: "secondary" as const },
    { label: "market", v: row.market_preference_score, color: "primary" as const },
  ];
  return (
    <Stack direction="row" gap={0.5} flexWrap="wrap">
      {items.map((i) => (
        <Chip
          key={i.label}
          size="small"
          color={i.color}
          variant="outlined"
          label={`${i.label} ${(i.v * 100).toFixed(0)}`}
        />
      ))}
    </Stack>
  );
}

export default function DispatchPage() {
  const nav = useNavigate();
  const [trucks, setTrucks] = useState<Truck[]>([]);
  const [truckId, setTruckId] = useState<number | "">("");
  const [rank, setRank] = useState<RankResponse | null>(null);
  const [explanations, setExplanations] = useState<Record<number, string>>({});
  const [expanded, setExpanded] = useState<number | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const selected = trucks.find((t) => t.id === truckId);

  useEffect(() => {
    api
      .trucks()
      .then((t) => {
        setTrucks(t);
        if (t[0]) setTruckId(t[0].id);
      })
      .catch((e) => setError(String(e)));
    api.assignments().then(setAssignments).catch(() => undefined);
  }, []);

  async function runRank() {
    if (truckId === "") return;
    setBusy(true);
    setError("");
    setExplanations({});
    try {
      const data = await api.rank(Number(truckId));
      setRank(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function loadExplain() {
    if (!rank) return;
    setBusy(true);
    try {
      const data = await api.explain(rank.score_run_id);
      const map: Record<number, string> = {};
      for (const e of data.explanations) map[e.load_id] = e.explanation_text;
      setExplanations(map);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function offer(loadId: number) {
    if (truckId === "") return;
    const a = await api.createAssignment(loadId, Number(truckId));
    setAssignments((prev) => [...prev, a]);
  }

  async function advance(a: Assignment) {
    const next = NEXT[a.status];
    if (!next) return;
    const updated = await api.patchAssignment(a.id, next);
    setAssignments((prev) => prev.map((x) => (x.id === a.id ? updated : x)));
  }

  const columns: GridColDef[] = useMemo(
    () => [
      { field: "rank", headerName: "#", width: 60 },
      { field: "load_id", headerName: "Load", width: 80 },
      {
        field: "overall",
        headerName: "Score",
        width: 160,
        renderCell: (p) => (
          <Box width="100%" pr={1}>
            <Typography variant="caption">{(Number(p.value) * 100).toFixed(1)}%</Typography>
            <LinearProgress variant="determinate" value={Number(p.value) * 100} />
          </Box>
        ),
      },
      {
        field: "rate_per_mile",
        headerName: "$/mi",
        width: 80,
        valueFormatter: (v: number) => v?.toFixed?.(2) ?? v,
      },
      {
        field: "deadhead_miles",
        headerName: "DH mi",
        width: 80,
        valueFormatter: (v: number) => v?.toFixed?.(0) ?? v,
      },
      {
        field: "factors",
        headerName: "Factors",
        flex: 1,
        minWidth: 280,
        sortable: false,
        renderCell: (p) => <FactorChips row={p.row as RankResult} />,
      },
      {
        field: "actions",
        headerName: "",
        width: 200,
        sortable: false,
        renderCell: (p) => (
          <Stack direction="row" gap={1}>
            <Button size="small" onClick={() => setExpanded(p.row.load_id)}>
              Why?
            </Button>
            <Button size="small" variant="outlined" onClick={() => offer(p.row.load_id)}>
              Offer
            </Button>
          </Stack>
        ),
      },
    ],
    [truckId],
  );

  return (
    <Box>
      <AppBar position="static" elevation={0} color="transparent">
        <Toolbar>
          <Typography variant="h4" sx={{ flexGrow: 1, fontSize: "1.5rem" }}>
            HaulRank
          </Typography>
          <Button
            color="inherit"
            onClick={() => {
              localStorage.clear();
              nav("/login");
            }}
          >
            Sign out
          </Button>
        </Toolbar>
      </AppBar>

      <Box px={3} py={2}>
        <Stack direction={{ xs: "column", md: "row" }} gap={2} alignItems="center" mb={2}>
          <FormControl sx={{ minWidth: 280 }}>
            <InputLabel>Truck</InputLabel>
            <Select
              label="Truck"
              value={truckId}
              onChange={(e) => setTruckId(e.target.value as number)}
            >
              {trucks.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  #{t.id} {t.equipment_type} · HOS{" "}
                  {t.driver?.hos_hours_remaining ?? "?"}h · ({t.current_lat.toFixed(2)},{" "}
                  {t.current_lon.toFixed(2)})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button variant="contained" onClick={runRank} disabled={busy || truckId === ""}>
            Rank loads
          </Button>
          <Button
            variant="outlined"
            onClick={loadExplain}
            disabled={busy || !rank}
          >
            Explain top 3
          </Button>
          {selected?.driver && (
            <Typography color="text.secondary">
              Preferred: {(selected.driver.preferred_markets || []).join(", ") || "—"}
            </Typography>
          )}
        </Stack>

        {error && (
          <Typography color="error" mb={2}>
            {error}
          </Typography>
        )}
        {busy && <LinearProgress sx={{ mb: 2 }} />}

        <Box height={420} mb={2}>
          <DataGrid
            rows={rank?.results ?? []}
            columns={columns}
            getRowId={(r) => r.load_id}
            disableRowSelectionOnClick
            pageSizeOptions={[10, 25]}
            initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
          />
        </Box>

        <Collapse in={expanded != null}>
          <Box mb={3} p={2} bgcolor="background.paper" borderRadius={1}>
            <Typography variant="subtitle1" gutterBottom>
              Why load #{expanded}?
            </Typography>
            {rank &&
              (() => {
                const row = rank.results.find((r) => r.load_id === expanded);
                if (!row) return null;
                return (
                  <>
                    <FactorChips row={row} />
                    <Typography mt={1} variant="body2">
                      overall={row.overall.toFixed(3)} · $/mi={row.rate_per_mile.toFixed(2)} ·
                      deadhead={row.deadhead_miles.toFixed(1)} mi
                    </Typography>
                    <Typography mt={1}>
                      {explanations[row.load_id] ||
                        "Click “Explain top 3” for an LLM narration of the stored numbers."}
                    </Typography>
                  </>
                );
              })()}
            <Button sx={{ mt: 1 }} onClick={() => setExpanded(null)}>
              Close
            </Button>
          </Box>
        </Collapse>

        <Typography variant="h6" gutterBottom>
          Assignments
        </Typography>
        <AssignmentBoard items={assignments} onAdvance={advance} />
      </Box>
    </Box>
  );
}
