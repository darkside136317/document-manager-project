// The staff app's sidebar (SidebarNav.vue): one section per group, whose links stay hidden until the group's button opens it.
// Opening a group closes the others, so a flow asks for the link it needs and the group that holds it is opened then.
// Playwright leaves hidden elements out of role queries: "the user is not offered X" must count the hidden links too (navOffers),
// or it would pass for any link that sits in a closed group.
const sidebar = (page) => page.getByRole("navigation", { name: "Điều hướng chính" });

/** A sidebar link, visible: the group that holds it is opened first when it is closed. */
export async function navLink(page, name, { exact = false, timeout = 10000 } = {}) {
  const nav = sidebar(page);
  await nav.getByRole("link", { name, exact, includeHidden: true }).first().waitFor({ state: "attached", timeout });
  const toggle = nav.locator("section").filter({ has: page.getByRole("link", { name, exact, includeHidden: true }) })
    .getByRole("button").first();
  if ((await toggle.getAttribute("aria-expanded")) === "false") await toggle.click();
  const link = nav.getByRole("link", { name, exact }).first();
  await link.waitFor({ state: "visible", timeout });
  return link;
}

/** How many sidebar links of that name the user is offered, in an opened group or not. */
export const navOffers = (page, name, { exact = false } = {}) =>
  sidebar(page).getByRole("link", { name, exact, includeHidden: true }).count();

/** The button of a sidebar group; it carries the sum of the counters of its links. */
export const navGroup = (page, label) => sidebar(page).getByRole("button", { name: label }).first();
