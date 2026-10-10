import { sqliteTable, text } from "drizzle-orm/sqlite-core";
export const connections = sqliteTable("connections", {
  userId: text("user_id").primaryKey(),
  secret: text("secret").notNull(),
});
