export type PanelBusy = {
  chatBusy: boolean;
  studioBusy: boolean;
  addBusy: boolean;
  researchBusy: boolean;
};

export function panelLocks(state: PanelBusy) {
  return {
    chatSendDisabled: state.chatBusy,
    studioSkillsDisabled: state.studioBusy,
    studioModalLocked: state.studioBusy,
    sourceAddDisabled: state.addBusy,
    sourceResearchDisabled: state.researchBusy,
  };
}
