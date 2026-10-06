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
const messaging=firebase.messaging();
messaging.onBackgroundMessage((payload)=>{
  const title=payload?.notification?.title||"Last Demons";
  const options={
    body:payload?.notification?.body||"",
    icon:"/icon-192.png", badge:"/icon-192.png",
    data:{url:payload?.fcmOptions?.link||payload?.data?.url||"https://last-demons.web.app/"}
  };
  self.registration.showNotification(title,options);
});
self.addEventListener("notificationclick",(event)=>{
  event.notification.close();
  const url=event.notification?.data?.url||"https://last-demons.web.app/";
  event.waitUntil(clients.openWindow(url));
});
