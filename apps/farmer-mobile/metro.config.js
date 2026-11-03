const {getDefaultConfig}=require('expo/metro-config');
const path=require('path');
const config=getDefaultConfig(__dirname);
const root=path.resolve(__dirname,'../..');
config.watchFolders=[root];
config.resolver.nodeModulesPaths=[path.join(__dirname,'node_modules'),path.join(root,'node_modules')];
module.exports=config;
