import React, { useEffect, useRef, useState } from "react";

function App() {
  const [page, setPage] = useState("setup");
  const videoRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);

  const [recording, setRecording] = useState(false);
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [timeLeft, setTimeLeft] = useState(120);

  // ================= CAMERA SETUP =================
  useEffect(() => {
    async function setupCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: true,
        });

        streamRef.current = stream;

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        console.error("Camera error:", err);
      }
    }

    setupCamera();
  }, []);

  // Keep camera when page switches
  useEffect(() => {
    if (videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [page]);

  // ================= START INTERVIEW =================
  const startInterview = async () => {
    const res = await fetch("http://localhost:8000/start", {
      method: "POST",
    });

    const data = await res.json();
    setSessionId(data.session_id);
    setQuestion(data.question);
  };

  // ================= RECORDING =================
  const startRecording = () => {
    if (!streamRef.current) return;

    const recorder = new MediaRecorder(streamRef.current);
    mediaRecorderRef.current = recorder;

    let chunks = [];

    recorder.ondataavailable = (e) => {
      chunks.push(e.data);
    };

    recorder.onstop = async () => {
      const blob = new Blob(chunks, { type: "video/webm" });

      const formData = new FormData();
      formData.append("file", blob);

      const res = await fetch(
        `http://localhost:8000/upload/${sessionId}`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await res.json();
      setQuestion(data.next_question);
      setTimeLeft(120);
    };

    recorder.start();
    setRecording(true);
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
    }
    setRecording(false);
  };

  // ================= TIMER =================
  useEffect(() => {
    if (!recording) return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          stopRecording();
          return 120;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [recording]);

  // ================= UI =================
  return (
    <div style={styles.page}>

      {/* SETUP PAGE */}
      {page === "setup" && (
        <div style={styles.card}>
          <h1 style={styles.title}>AI Technical Interview Coach</h1>

          <textarea
            placeholder="Paste job description here..."
            style={styles.textarea}
          />

          <div style={styles.uploadBox}>
            Upload Resume (Optional)
          </div>

          <div style={styles.videoPreview}>
            <video
              ref={videoRef}
              autoPlay
              muted
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover"
              }}
            />
          </div>

          <button
            style={styles.primaryBtn}
            onClick={async () => {
              await startInterview();
              setPage("interview");
            }}
          >
            Start Interview
          </button>
        </div>
      )}

      {/* INTERVIEW PAGE */}
      {page === "interview" && (
        <div style={styles.interviewContainer}>

          <div style={styles.timer}>
            ⏱ {timeLeft}s
          </div>

          <div style={styles.avatar}>
            <div style={styles.avatarCircle}>AI</div>
          </div>

          <div style={styles.camera}>
            <video
              ref={videoRef}
              autoPlay
              muted
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover"
              }}
            />
          </div>

          <div style={styles.questionBox}>
            <h2>{question}</h2>

            <div style={{ display: "flex", gap: "10px", marginTop: "20px" }}>
              {!recording ? (
                <button style={styles.greenBtn} onClick={startRecording}>
                  Start My Answer
                </button>
              ) : (
                <button style={styles.redBtn} onClick={stopRecording}>
                  Stop My Answer
                </button>
              )}

              <button
                style={styles.grayBtn}
                onClick={() => setPage("results")}
              >
                Finish Interview
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RESULTS PAGE */}
      {page === "results" && (
        <div style={styles.resultsCard}>
          <h1>Interview Complete 🎉</h1>

          <div style={styles.resultBox}>
            <p><strong>Last Question:</strong></p>
            <p>{question}</p>
          </div>

          <button
            style={styles.primaryBtn}
            onClick={() => setPage("setup")}
          >
            Start Again
          </button>
        </div>
      )}

    </div>
  );
}

// ================= STYLES =================
const styles = {
  page: {
    minHeight: "100vh",
    backgroundColor: "#F4F6F8",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    fontFamily: "Arial"
  },
  card: {
    width: "600px",
    background: "white",
    padding: "30px",
    borderRadius: "12px",
    boxShadow: "0 10px 30px rgba(0,0,0,0.1)",
    display: "flex",
    flexDirection: "column",
    gap: "20px"
  },
  title: { textAlign: "center" },
  textarea: {
    minHeight: "150px",
    padding: "10px",
    borderRadius: "8px",
    border: "1px solid #ccc"
  },
  uploadBox: {
    border: "2px dashed #ccc",
    padding: "20px",
    textAlign: "center",
    borderRadius: "8px"
  },
  videoPreview: {
    width: "100%",
    aspectRatio: "16 / 9",
    backgroundColor: "#000",
    borderRadius: "8px",
    overflow: "hidden"
  },
  primaryBtn: {
    padding: "12px",
    backgroundColor: "#1E88E5",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer"
  },
  interviewContainer: {
  width: "100%",
  height: "100vh",
  backgroundColor: "#F4F6F8",
  display: "flex",
  flexDirection: "column",
  overflow: "hidden"
  },
  timer: {
    position: "absolute",
    top: "20px",
    left: "20px",
    backgroundColor: "black",
    color: "white",
    padding: "8px 15px",
    borderRadius: "20px"
  },
  avatar: {
    position: "absolute",
    top: "20px",
    right: "20px"
  },
  avatarCircle: {
    width: "60px",
    height: "60px",
    borderRadius: "50%",
    backgroundColor: "#1E88E5",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    color: "white",
    fontWeight: "bold"
  },
  camera: {
  height: "65vh",
  backgroundColor: "black",
  position: "relative"
},
  questionBox: {
  height: "35vh",
  backgroundColor: "white",
  padding: "20px",
  overflowY: "auto",
  borderTop: "1px solid #ddd"
},
  greenBtn: {
    padding: "10px 20px",
    backgroundColor: "#43A047",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer"
  },
  redBtn: {
    padding: "10px 20px",
    backgroundColor: "#E53935",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer"
  },
  grayBtn: {
    padding: "10px 20px",
    backgroundColor: "#ccc",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer"
  },
  resultsCard: {
    width: "800px",
    background: "white",
    padding: "30px",
    borderRadius: "12px",
    boxShadow: "0 10px 30px rgba(0,0,0,0.1)",
    display: "flex",
    flexDirection: "column",
    gap: "20px"
  },
  resultBox: {
    backgroundColor: "#f9f9f9",
    padding: "20px",
    borderRadius: "8px"
  }
};

export default App;