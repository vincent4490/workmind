/* jshint esversion: 6 */
import { createStore } from "vuex";
import state from "./state";
import mutations from "./mutations";
import actions from "@/store/actions";

const store = createStore({
    state,
    mutations,
    actions
})

export default store
