/** Mount the React app and optionally report browser performance metrics. */
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import DesignPreview from './DesignPreview';
import './product-polish.css';
import reportWebVitals from './reportWebVitals';
const preview = process.env.NODE_ENV === 'development' && new URLSearchParams(window.location.search).has('design');


const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    {preview ? <DesignPreview /> : <App />}
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();


