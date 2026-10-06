
importScripts("https://www.gstatic.com/firebasejs/11.0.2/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/11.0.2/firebase-messaging-compat.js");
firebase.initializeApp({
  apiKey: "AIzaSyDKe8SyAjMfDY9UavENY5ywcVyK_JZetWE",
  authDomain: "last-demons.firebaseapp.com",
  projectId: "last-demons",
  storageBucket: "last-demons.firebasestorage.app",
  messagingSenderId: "36761061003",
  appId: "1:36761061003:web:dec18c5ee7757beb1e768e"
});
const messaging = firebase.messaging();
messaging.onBackgroundMessage((payload) => {
  const n = payload.notification || {};
  self.registration.showNotification(n.title || "Last Demons", {
    body: n.body || "Hai una nuova notifica.",
    icon: "/favicon.png",
    badge: "/favicon.png",
    data: payload.data || {}
  });
});
