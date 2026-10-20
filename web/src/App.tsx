import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { SnackbarProvider } from "notistack";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import { green } from "@mui/material/colors";
import Fade from "@mui/material/Fade";

import GameScreen from "./pages/GameScreen";
import HomePage from "./pages/HomePage";
import { StateProvider } from "./store";

import "./App.scss";
import ReplayScreen from "./pages/ReplayScreen";

const theme = createTheme({
  breakpoints: {
    values: { xs: 0, sm: 600, md: 960, lg: 1280, xl: 1920 },
  },
  palette: {
    primary: {
      main: "#c4922a",
      contrastText: "#1c1406",
    },
    secondary: {
      main: green[800],
    },
  },
  typography: {
    button: {
      textTransform: "none",
      fontWeight: 600,
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <StateProvider>
        <SnackbarProvider
          classes={{ containerRoot: "snackbar-container" }}
          maxSnack={1}
          autoHideDuration={1000}
          TransitionComponent={Fade}
          TransitionProps={{ timeout: 100 }}
        >
          <Router>
            <Routes>
              <Route
                path="/games/:gameId/states/:stateIndex"
                element={<GameScreen replayMode={true} />}
              />
              <Route path="/replays/:gameId" element={<ReplayScreen />} />
              <Route
                path="/games/:gameId"
                element={<GameScreen replayMode={false} />}
              />
              <Route path="/" element={<HomePage />} />
            </Routes>
          </Router>
        </SnackbarProvider>
      </StateProvider>
    </ThemeProvider>
  );
}

export default App;
