import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Button,
  Checkbox,
  IconButton,
  Slider,
  Tooltip,
} from "@mui/material";
import HelpOutlineRoundedIcon from "@mui/icons-material/HelpOutlineRounded";
import { GridLoader } from "react-spinners";
import PlayerSetup from "../components/PlayerSetup";
import {
  createGame,
  getGames,
  getPlayers,
  type MapTemplate,
  type PlayerEntry,
  type PlayerKey,
  type PlayerSpec,
  type SavedGame,
} from "../utils/apiClient";

import "./HomePage.scss";

const MAP_TEMPLATES: MapTemplate[] = ["BASE", "MINI", "TOURNAMENT"];
const PLAYER_COLORS = ["RED", "BLUE", "ORANGE", "WHITE"] as const;

export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [mapTemplate, setMapTemplate] = useState<MapTemplate>("BASE");
  const [vpsToWin, setVpsToWin] = useState(10);
  const [discardLimit, setDiscardLimit] = useState(7);
  const [friendlyRobber, setFriendlyRobber] = useState(false);
  const [players, setPlayers] = useState<PlayerSpec[]>([
    { key: "HUMAN", params: {} },
    { key: "CATANATRON", params: {} },
    { key: "CATANATRON", params: {} },
  ]);
  const [available, setAvailable] = useState<PlayerEntry[]>([]);
  const [savedGames, setSavedGames] = useState<SavedGame[]>([]);
  const [startError, setStartError] = useState<string | null>(null);
  const navigate = useNavigate();

  // The server decides which players exist; the UI no longer hardcodes them.
  useEffect(() => {
    getPlayers()
      .then((entries) =>
        setAvailable(entries.filter((entry) => entry.key !== "H")),
      )
      .catch(() => setAvailable([]));
    getGames()
      .then(setSavedGames)
      .catch(() => setSavedGames([]));
  }, []);

  const humanKeys = useMemo(
    () => new Set(available.filter((entry) => !entry.is_bot).map((e) => e.key)),
    [available],
  );
  const isHuman = (key: PlayerKey) => humanKeys.has(key);
  const humanCount = players.filter((player) => isHuman(player.key)).length;
  const hasInvalidHumanCount = humanCount !== 1;
  const hasInvalidBotParams = players.some((player) => {
    const entry = available.find((option) => option.key === player.key);
    return entry?.params.some((param) => {
      const value = Object.prototype.hasOwnProperty.call(
        player.params,
        param.name,
      )
        ? player.params[param.name]
        : param.default;
      if (value === null) {
        return param.default !== null;
      }
      return (
        (param.type === "int" || param.type === "float") &&
        (typeof value !== "number" || !Number.isFinite(value))
      );
    });
  });

  const playerSpec = (key: PlayerKey): PlayerSpec => {
    const entry = available.find((option) => option.key === key);
    return {
      key,
      params: Object.fromEntries(
        (entry?.params ?? []).map((param) => [param.name, param.default]),
      ),
    };
  };

  const handlePlayerChange = (index: number, value: PlayerKey) => {
    if (isHuman(value) && !isHuman(players[index].key) && humanCount >= 1) {
      return;
    }

    setPlayers((current) =>
      current.map((player, playerIndex) =>
        playerIndex === index ? playerSpec(value) : player,
      ),
    );
  };

  const handlePlayerParamChange = (
    index: number,
    name: string,
    value: number | string | boolean | null,
  ) => {
    setPlayers((current) =>
      current.map((player, playerIndex) =>
        playerIndex === index
          ? { ...player, params: { ...player.params, [name]: value } }
          : player,
      ),
    );
  };

  const handleAddPlayer = () => {
    setPlayers((current) =>
      current.length >= 4 ? current : [...current, playerSpec("CATANATRON")],
    );
  };

  const handleRemovePlayer = (index: number) => {
    setPlayers((current) =>
      current.length <= 3
        ? current
        : current.filter((_, playerIndex) => playerIndex !== index),
    );
  };

  const handleCreateGame = async () => {
    if (hasInvalidHumanCount || hasInvalidBotParams || players.length < 3) {
      return;
    }

    setLoading(true);
    setStartError(null);
    try {
      const gameId = await createGame({
        players,
        mapTemplate,
        vpsToWin,
        discardLimit,
        friendlyRobber,
      });
      navigate("/games/" + gameId);
    } catch {
      setStartError("Could not start the game. Check the player settings.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="home-page">
      <div className="home-page__inner">
        <h1 className="logo">Catan Coach</h1>
        {!loading ? (
          <>
            {savedGames.length > 0 && (
              <section className="saved-games">
                <div className="control-header">
                  <span>Saved games</span>
                  <strong>{savedGames.length}</strong>
                </div>
                {savedGames.map((game) => (
                  <Button
                    key={game.game_id}
                    className="saved-game"
                    onClick={() =>
                      navigate(
                        game.status === "finished"
                          ? `/replays/${game.game_id}`
                          : `/games/${game.game_id}`,
                      )
                    }
                  >
                    <span>
                      {game.players.join(" vs ")} · {game.state_index} Actions
                    </span>
                    <strong>
                      {game.status === "finished"
                        ? `${game.winning_color} won`
                        : "Continue"}
                    </strong>
                  </Button>
                ))}
              </section>
            )}
            <div className="setup-card">
              <p className="setup-note">Open hands. Random discard choice.</p>

              <div className="control-group">
                <div className="control-header">
                  <span>Map Template</span>
                  <strong>{mapTemplate}</strong>
                </div>
                <div className="map-template-buttons">
                  {MAP_TEMPLATES.map((value) => (
                    <Button
                      key={value}
                      variant="contained"
                      onClick={() => setMapTemplate(value)}
                      className={`choice-button ${
                        mapTemplate === value ? "selected" : ""
                      }`}
                    >
                      {value}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="control-row">
                <div className="control-group compact-control">
                  <div className="control-header">
                    <span>Points to Win</span>
                    <strong>{vpsToWin}</strong>
                  </div>
                  <Slider
                    value={vpsToWin}
                    min={3}
                    max={20}
                    step={1}
                    marks
                    valueLabelDisplay="auto"
                    onChange={(_, value) => setVpsToWin(value as number)}
                  />
                </div>

                <div className="control-group compact-control">
                  <div className="control-header">
                    <span>Card Discard Limit</span>
                    <strong>{discardLimit}</strong>
                  </div>
                  <Slider
                    value={discardLimit}
                    min={5}
                    max={20}
                    step={1}
                    marks
                    valueLabelDisplay="auto"
                    onChange={(_, value) => setDiscardLimit(value as number)}
                  />
                </div>

                <div className="control-group compact-control switch-control">
                  <div className="control-header">
                    <span className="inline-title">
                      Friendly Robber
                      <Tooltip
                        title="Prevent robber placement on tiles touching opponents with 2 victory points."
                        arrow
                        enterTouchDelay={0}
                        leaveTouchDelay={3000}
                      >
                        <IconButton
                          size="small"
                          className="help-button"
                          aria-label="Friendly Robber help"
                        >
                          <HelpOutlineRoundedIcon fontSize="inherit" />
                        </IconButton>
                      </Tooltip>
                    </span>
                    <strong>{friendlyRobber ? "On" : "Off"}</strong>
                  </div>
                  <Checkbox
                    className="inline-switch"
                    checked={friendlyRobber}
                    onChange={(event) =>
                      setFriendlyRobber(event.target.checked)
                    }
                  />
                </div>
              </div>

              <div className="control-group">
                <div className="control-header">
                  <span>Players</span>
                  <strong>{players.length}/4</strong>
                </div>
                {hasInvalidHumanCount && (
                  <Alert severity="error" className="players-alert">
                    Exactly one Human player is required.
                  </Alert>
                )}
                {hasInvalidBotParams && (
                  <Alert severity="error" className="players-alert">
                    Bot parameters must be valid numbers.
                  </Alert>
                )}
                {startError && (
                  <Alert severity="error" className="players-alert">
                    {startError}
                  </Alert>
                )}
                <div className="players-list">
                  {players.map((player, index) => (
                    <PlayerSetup
                      key={`${player.key}-${index}`}
                      color={PLAYER_COLORS[index]}
                      index={index}
                      player={player}
                      available={available}
                      humanKeys={humanKeys}
                      humanCount={humanCount}
                      canRemove={players.length > 3}
                      onPlayerChange={(key) => handlePlayerChange(index, key)}
                      onParamChange={(name, value) =>
                        handlePlayerParamChange(index, name, value)
                      }
                      onRemove={() => handleRemovePlayer(index)}
                    />
                  ))}
                </div>

                <Button
                  variant="contained"
                  className="add-player-btn"
                  disabled={players.length >= 4}
                  onClick={handleAddPlayer}
                >
                  Add Player
                </Button>
              </div>

              <Button
                variant="contained"
                color="primary"
                className="start-btn"
                disabled={
                  hasInvalidHumanCount ||
                  hasInvalidBotParams ||
                  players.length < 3
                }
                onClick={handleCreateGame}
              >
                Start
              </Button>
            </div>
          </>
        ) : (
          <GridLoader className="loader" color="#ffffff" size={60} />
        )}
        <div className="page-end-spacer" aria-hidden="true" />
      </div>
    </div>
  );
}
