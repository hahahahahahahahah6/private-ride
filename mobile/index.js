import { registerRootComponent } from "expo";
import App from "./App";

// Expo 入口：注册根组件（以前 main 直接指向 App.js，没人注册，App 打开是白屏）
registerRootComponent(App);
